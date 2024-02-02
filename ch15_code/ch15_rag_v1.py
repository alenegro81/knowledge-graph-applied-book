import os
import time
import json
from pprint import pprint

from langchain_community.graphs import Neo4jGraph
from langchain.prompts import PromptTemplate
from langchain.vectorstores.neo4j_vector import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA, GraphCypherQAChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langchain.agents import create_react_agent, Tool, AgentExecutor
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_community.tools.convert_to_openai import format_tool_to_openai_tool
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages

NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "rac12345"
NEO4J_DB = "rac2"

OPENAI_API_KEY = "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"
#MODEL = "gpt-3.5-turbo"
MODEL = "gpt-4"

# Azure OpenAI
api_key = "d28eb2ef49754a3796f970de6fb8809a"
#openai.api_type = "azure"
api_base = "https://ga-sandbox.openai.azure.com"
api_version = "2023-12-01-preview"

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
    os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

    graph = Neo4jGraph(
        url=NEO4J_URL,
        username=NEO4J_USER,
        password=NEO4J_PWD,
        database=NEO4J_DB
    ) # requires APOC to be installed, specifically `apoc.meta.data`

    #print(graph.query("MATCH (n) RETURN count(*)"))

    vector_index = Neo4jVector.from_existing_graph(
        OpenAIEmbeddings(),
        url=NEO4J_URL,
        username=NEO4J_USER,
        password=NEO4J_PWD,
        database=NEO4J_DB,
        index_name='embeddings',
        node_label="Page",
        text_node_properties=['text'],
        embedding_node_property='embedding'
    )

    #question = "Who are the top influencers of cyclotron funding?"
    #question = "What did August Krogh say about Lawrence Irving?"
    #response = vector_index.similarity_search(question, k=3) # k = number of results to return; score_threshold=0.9 - doesn't seem to work
    #for i in range(3):
    #    print(response[i].page_content)

    vector_qa = RetrievalQA.from_chain_type(
        llm=ChatOpenAI(model_name=MODEL, temperature=0.2),
        chain_type="stuff",
        retriever=vector_index.as_retriever(k=3, score_threshold=0.9)
    )
    #response = vector_qa.invoke(question)
    #print(f"### RAG(vector) response: {response['result']}")

    graph.refresh_schema()
    #print(graph.schema)

    #question = "Who worked on cyclotron?"
    cypher_chain = GraphCypherQAChain.from_llm(
        cypher_llm=ChatOpenAI(model_name=MODEL, temperature=0),
        qa_llm=ChatOpenAI(model_name=MODEL, temperature=0.4),
        graph=graph,
        qa_prompt=CYPHER_QA_PROMPT,
        verbose=True
    )
    #response = cypher_chain.invoke(question)
    #print(f"### RAG response: {response['result']}")

    tools = [
        Tool(
            name="Diaries",
            func=vector_qa.invoke,
            description="""Useful when you need to answer questions about content of Warren Weaver's diaries 
            that is too detailed to be modeled in the Knowledge Graph. For example, when we want to know who said what.
            Not useful for questions that can be answered by querying the Knowledge Graph tool.
            Note that the diaries often abbreviate people names, for e.g. after the diary entry introduces "John Snow", it often refers to him later on simply as "S."
            Always use full question as input, without any changes!""", # without this, it will simplify the question or even search for simple keywords such as "August Krogh"
        ),
        Tool(
            name="KnowledgeGraph",
            func=cypher_chain.invoke,
            description="""Useful when you need to answer questions about how are entities such as people, 
            organizations and occupations related.
            Also useful for any sort of aggregation like counting the number of people per occupation etc.
            
            Full Knowledge Graph schema in Cypher syntax to help you decide whether this tool can be used or not:
            (:Person)-[:WORKS_FOR]->(:Organization)
            (:Person)-[:WORKS_WITH]->(:Person)
            (:Person)-[:TALKED_WITH]->(:Person)
            (:Person)-[:TALKED_ABOUT]->(:Person)
            (:Person)-[:WORKS_ON]->(:Occupation)
            (:Occupation)-[:SIMILAR_OCCUPATION]->(:Occupation)
            (:Organization)-[:SIMILAR_ORGANNIZATION]->(:Organization)
            
            Always use full question as input, without any changes!""",
        )
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are very powerful assistant, but don't know current events nor details about"
                "Rockefeller Foundation grants in 1930s.",
            ),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm = ChatOpenAI(temperature=0,
                     #model="gpt-3.5-turbo" # fails to pass full question to the KG tool
                     model = "gpt-4"
                     )
    llm_with_tools = llm.bind(tools=[format_tool_to_openai_tool(tool) for tool in tools])

    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(x["intermediate_steps"]),
        }
        | prompt
        | llm_with_tools
        | OpenAIToolsAgentOutputParser()
    )

    #question = "Who are the top influencers of cyclotron research?"
    #question = "What did August Krogh say about Lawrence Irving?"
    question = "Who worked on cyclotron research?"
    #question = "Who worked on cyclotron and what is known about them?"

    agent_executor = AgentExecutor(agent=agent, tools=tools, return_intermediate_steps=True, verbose=True)
    response = agent_executor.invoke({"input": question})

    #print("### Intermediate steps:")
    #pprint(response['intermediate_steps'])
    #print(f"### Agent's response: {response}")
    print(f"\n### Agent's response: {response['output']}")
