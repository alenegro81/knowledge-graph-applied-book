import os
import sys
import time
import json
from pprint import pprint
from dotenv import load_dotenv

from langchain import hub
from langchain_community.graphs import Neo4jGraph
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI, OpenAI
from langchain.chains import RetrievalQA, GraphCypherQAChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool

from langchain.agents import create_structured_chat_agent, Tool, AgentExecutor
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_community.tools.convert_to_openai import format_tool_to_openai_tool
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages

from definitions import KG_SCHEMA
from document_selector_re import REDiarySelectorTool, kg_doc_selector, REDiarySelectorInput
from tools import vector_search, kg_reader, VectorSearchInput, KGReaderInput

#MODEL = "gpt-3.5-turbo"
#MODEL = "gpt-4"
MODEL = "gpt-4o-mini"

# Needed to override the default answer-generation prompt since it was unstable:
# - worked - RETURN p: [{'p': {'name': 'E. Fermi', 'count': 7, 'name_normalized': 'e. fermi', 'titles': ['Professor']}}, {'p': {'pr_influencers': 0.4315390146456121, 'wcc': 0, 'name': 'R. W. Hickman', 'count': 5, 'eigen_influencers': 0.001961289393970275, 'betweenness': 0.0, 'name_normalized': 'r. w. hickman', 'pagerank': 0.45768709319333833, 'eigenvector': 0.0010072011640782964}}, {'p': {'name': 'R. C. Gibbs', 'count': 10, 'name_normalized': 'r. c. gibbs', 'titles': ['Professor']}}, {'p': {'wcc': 113, 'name': 'R. J. Van de Graaff', 'count': 21, 'titles': ['Dr.'], 'name_normalized': 'r. j. van de graaff'}}, {'p': {'wcc': 345, 'name': 'Karl Lark-Horovitz', 'count': 13, 'titles': ['Professor'], 'name_normalized': 'karl lark-horovitz'}}, {'p': {'pr_influencers': 7.332354892368005, 'wcc': 0, 'name': 'Ernest Orlando Lawrence', 'count': 36, 'eigen_influencers': 0.09976117416193767, 'betweenness': 20106.39398389481, 'titles': [], 'name_normalized': 'ernest orlando lawrence', 'pagerank': 6.596601218415963, 'eigenvector': 0.050068108161504345}}]
# - didn't work - RETURN p.name: [{'p.name': 'E. Fermi'}, {'p.name': 'R. W. Hickman'}, {'p.name': 'R. C. Gibbs'}, {'p.name': 'R. J. Van de Graaff'}, {'p.name': 'Karl Lark-Horovitz'}, {'p.name': 'Ernest Orlando Lawrence'}]
CYPHER_QA_TEMPLATE = """You are an assistant that helps to form nice and human understandable answers grounded in contextual knowledge extracted by Cypher query from a Knowledge Graph.
The contextual knowledge part must be used to construct an answer and it is authoritative: you must never doubt it or try to use your internal knowledge to correct it.
Make the answer sound as a response to the question. Do not mention that you based the result on the given information.
If the provided information is empty, say that you don't know the answer.

Question: {question}

Contextual Knowledge (from a Knowledge Graph):
{context}

Helpful Concise Answer:"""
CYPHER_QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"], template=CYPHER_QA_TEMPLATE
)


if __name__ == "__main__":
    #os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY
    load_dotenv()

    graph = Neo4jGraph(
        url=os.environ['NEO4J_URL'],
        username=os.environ['NEO4J_USER'],
        password=os.environ['NEO4J_PWD'],
        database=os.environ['NEO4J_DB']
    ) # requires APOC to be installed, specifically `apoc.meta.data`

    #print(graph.query("MATCH (n) RETURN count(*) AS count"))

    vector_index = Neo4jVector.from_existing_graph(
        OpenAIEmbeddings(),
        url=os.environ['NEO4J_URL'],
        username=os.environ['NEO4J_USER'],
        password=os.environ['NEO4J_PWD'],
        database=os.environ['NEO4J_DB'],
        index_name='embeddings',
        node_label="Page",
        text_node_properties=['text'],
        embedding_node_property='embedding'
    )

    #question = "Who are the top influencers of cyclotron funding?"
    #question = "What did August Krogh say about Lawrence Irving?"
    question = "How is Lauritsen related to cyclotron?"
    response = vector_index.similarity_search_with_score(question, k=3) # k = number of results to return; score_threshold=0.9 - doesn't seem to work
    for r in response:
        print(f"Score: {r[1]}")
        print(r[0].page_content)
    sys.exit()

    vector_qa = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(model_name=MODEL, temperature=0.2),
        chain_type="stuff",
        retriever=vector_index.as_retriever(k=3, score_threshold=0.9)
    )
    # response = vector_qa.invoke(question)
    # print(f"### RAG(vector) response: {response['result']}")
    # sys.exit()

    graph.refresh_schema()
    #print(graph.schema)

    #question = "Who worked on cyclotron?"
    cypher_chain = GraphCypherQAChain.from_llm(
        cypher_llm=ChatOpenAI(model_name=MODEL, temperature=0),
        qa_llm=ChatOpenAI(model_name=MODEL, temperature=0.2),
        graph=graph,
        qa_prompt=CYPHER_QA_PROMPT,
        verbose=True,
        allow_dangerous_requests=True # narrowly scope the permissions of the database connection to only include necessary permissions. Failure to do so may result in data corruption or loss or reading sensitive data
    )
    #response = cypher_chain.invoke(question)
    #print(f"### RAG response: {response['result']}")

    tools = [
        StructuredTool.from_function(
            #func=vector_qa.invoke,
            func=vector_search,
            name="Diaries-vector-search",
            args_schema=VectorSearchInput,
            return_direct=False,
            description="""This is a backup tool based on vector search to be used ONLY when no other tool provides nor  
            is capable to provide question-relevant context.
            Try the other tools first! Then use this one as a last resort.
            Use it when you need to answer questions about details within Warren Weaver's diaries that are too
            fine-grained to be modeled in the Knowledge Graph.
            When the other tools return nothing useful, execute this tool before generating final answer.
            Always use full question as input, without any changes!""",
            # "For example, when we want to know who said what."
            #"""Note that the diaries often abbreviate people names, for e.g. after the diary entry introduces "John Snow",
            #it often refers to him later on simply as "S.""""
        ),
        StructuredTool.from_function(
            func=kg_reader,
            name="KnowledgeGraph-reader",
            args_schema=KGReaderInput,
            description=f"""Useful when you need to answer questions for which the information stored in the KG
            is sufficient, for example about relationships among entities such as people, organizations and occupations.
            Also useful for any sort of aggregation like counting the number of people per occupation etc.
            This tool translates the question into a Cypher query, executes it and returns results.

            Full Knowledge Graph schema in Cypher syntax to help you decide whether this tool can be used or not:
            {KG_SCHEMA}

            Always use full question as input, without any changes!""",
        ),
        StructuredTool.from_function(
            func=kg_doc_selector,
            name="KG-based-document-selector",
            args_schema=REDiarySelectorInput,
            return_direct=False,
            description=(
                "Use this as a default tool for document (diary entries) retrieval when the question asks for detailed "
                "information regarding interaction between two entities. "
                "The entities and relationship between them must be modeled within the KG (see schema below), but the KG itself "
                "does not contain enough details to provide the answer (in which case you should use the "
                "KnowledgeGraph-reader tool.\n\n"
                "Full Knowledge Graph schema in Cypher syntax to help you decide whether this tool can be used or not:\n"
                f"{KG_SCHEMA}"
                #"\n\nIf this tool returns nothing useful, use the backup tool.
            )
        )
    ]

    llm = ChatOpenAI(model=MODEL, temperature=0)

    #react_prompt = hub.pull("hwchase17/structured-chat-agent")
    with open("prompt_structured.txt", 'r') as f:
        system = f.read()
        human = ("{input}\n\n"
                 "{agent_scratchpad}\n\n"
                 "(reminder to respond in a JSON blob no matter what)")
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", human),
            ]
        )
    agent = create_structured_chat_agent(llm, tools, prompt)

    #question = "Who are the top three influencers of cyclotron research?"# and what is known about them?"
    #question = "What did August Krogh say about Lawrence Irving?"
    #question = "What did Ernest Orlando Lawrence and Niels Bohr talk about?"
    #question = "Who worked on cyclotron research?" # existing Occupations: cyclotron, cyclotron program, cyclotron project, 100,000,000 to 200,000,000 volt cyclotron
    #question = "Who worked on cyclotron and what is known about them?"
    ##question = "What did people in cyclotron research think of Lawrence?"
    ##question = "How did people in cyclotron research perceive Lawrence?"
    ##question = "Who are the people connecting Harvard and Johns Hopkins University?"
    #question = "Are there any shared research topics between Harvard and Johns Hopkins University?"
    #question = "How was Dorothy M. Wrinch being described by her colleagues?"
    #question = "How is Lawrence related to University of California?"
    question = "How is Lauritsen related to cyclotron?"


    agent_executor = AgentExecutor(agent=agent, tools=tools, max_iterations=5,
                                   return_intermediate_steps=True, verbose=True)
                                #handle_parsing_errors=True # pass an error (in a tool) back to the agent and have it try again
    response = agent_executor.invoke({"input": question})

    # pprint(f"\n### Agent's intermediate steps:\n")
    # for i, step in enumerate(response['intermediate_steps']):
    #     print(f"\n--- Step {i}")
    #     #print(f"---step[1]: {step[1]}") # output of this step (tool)
    #     for j, m in enumerate(step[0].messages):
    #         #print(f"--- Step {i}, Message {j}")
    #         print(m.pretty_repr())
    print(f"\n### Agent's response: {response['output']}")
