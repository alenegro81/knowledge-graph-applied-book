import os
from pprint import pprint
from dotenv import load_dotenv
from typing import List, AnyStr

from langchain_openai import OpenAIEmbeddings
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from langchain_core.tools import StructuredTool
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from pydantic import BaseModel, Field

from definitions import KG_SCHEMA


class VectorSearchInput(BaseModel):
    question: str = Field(description="User's question / search query.")

#@StructuredTool("Diaries-vector-search", args_schema=VectorSearchInput, return_direct=False)
def vector_search(question: str) -> List[AnyStr]:
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

    response = vector_index.similarity_search_with_score(question, k=3) # score_threshold=0.9 - doesn't seem to work

    return [r[0].page_content for r in response] # r[1] is a score


class KGReaderInput(BaseModel):
    question: str = Field(description="User's question / search query.")


def kg_reader(question: str) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    prompt = PromptTemplate(input_variables=['question'], template=(
        "From the natural language question provided below, generate a Cypher query to run against a Neo4j DB\n"
        f"with the following schema:\n{KG_SCHEMA}\n\n"
        f"Use only entity classes, relationship types and properties indicated in the schema.\n"
        "When searching through Person node names, but only surname is provided, always use CONTAINS operator instead of "
        "exact matching, i.e. `MATCH ...(p:Person)... WHERE p.name CONTAINS \"<surname>\"``.\n"
        "When searching through Occupation nodes names, use CONTAINS operator instead of exact matching, and remove any"
        "unnecessary words that could make it harder to match all relevant Occupations.\n"
        "Important note: Output only the Cypher query, that is all that's required. If you're unable to\n"
        "generate it, return an empty string.\n\n"
        "The question is:\n{question}\n\n"
        #"Note: where relevant, always RETURN full matched paths so that the subsequent LLM generating textual answer "
        #"has all relevant information. " # Always return also relationship types.
        #"Important: In the generated Cypher query, the RETURN statement must explicitly include the property values "
        #"used in the query’s filtering condition, alongside the main information requested from the original question."
        #"By default, return whole paths."
        ))
    cypher_chain = prompt | llm

    graph = Neo4jGraph(
        url=os.environ['NEO4J_URL'],
        username=os.environ['NEO4J_USER'],
        password=os.environ['NEO4J_PWD'],
        database=os.environ['NEO4J_DB']
    )  # requires APOC to be installed, specifically `apoc.meta.data`

    # generate Cypher query
    cypher_query = cypher_chain.invoke({'question': question}).content
    print(f"kg_reader generated the following Cypher query:\n{cypher_query}")
    if len(cypher_query.strip()) == 0:
        return ""
    if cypher_query.lower().startswith("```cypher"):
        cypher_query = cypher_query[9:].strip()
    elif cypher_query.startswith("```"):
        cypher_query = cypher_query[3:].strip()
    if cypher_query.endswith("```"):
        cypher_query = cypher_query[:-3].strip()

    # execute Cypher
    try:
        res = graph.query(cypher_query)
        print(f"kg_reader found {len(res)} results")
    except Exception as e:
        print(f"Cypher execution exception: {e}")
        return "No results found."

    return f"Cypher query:\n{cypher_query}\n\nResponse from Neo4j:\n" + repr(res)


if __name__ == "__main__":
    load_dotenv()

    pprint(vector_search("What did August Krogh say about Lawrence Irving?"))