from typing import Optional, Type, List, AnyStr

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, StructuredTool
from langchain_community.graphs import Neo4jGraph
from langchain_core.tools import tool

from definitions import KG_SCHEMA


NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PWD = "rac12345"
NEO4J_DB = "rac2"

graph = Neo4jGraph(
        url=NEO4J_URL,
        username=NEO4J_USER,
        password=NEO4J_PWD,
        database=NEO4J_DB
    )  # requires APOC to be installed, specifically `apoc.meta.data`

RE_SELECTOR_QUERY = """MATCH (p:Page)-[:MENTIONS_ENTITY]->(m1:Entity)-->(e1:{e1_class})-[:{rel_class}]-(e2:{e2_class})<--(m2:Entity)<-[:MENTIONS_ENTITY]-(p)
WHERE e1.name = "{e1}" AND e2.name = "{e2}"
MATCH (m1)-[r:RELATED_TO_ENTITY]-(m2)
WHERE r.type = "{rel_class}"
RETURN DISTINCT p.id AS id, p.text AS text
"""


class REDiarySelectorInput(BaseModel):
    entity_source: str = Field(description="Source entity of the relationship as mentioned in the question.")
    entity_source_class: str = Field(description="Class of the source entity of the relationship. "
                                                 "Available option is only one, 'Person'."
                                    )
    entity_target: str = Field(description="Target entity of the relationship as mentioned in the question.")
    entity_target_class: str = Field(description="Class of the target entity of the relationship. "
                                                 "Available options are Person, Organization, Occupation and Title."
                                     )
    relationship: str = Field(description="Relationship class between source and target entity. "
                                       "Available options: TALKED_ABOUT, TALKED_WITH, WORKS_WITH, WORKS_ON, HAS_TITLE")


#@tool("KG-based-document-selector", args_schema=REDiarySelectorInput, return_direct=False)
def kg_doc_selector(entity_source: str, entity_source_class: str, entity_target: str, entity_target_class: str,
                    relationship: str) -> List[AnyStr]:
    query = RE_SELECTOR_QUERY.format(e1=entity_source, e1_class=entity_source_class,
                             e2=entity_target, e2_class=entity_target_class,
                             rel_class=relationship)
    print(f"kg_doc_selector's query:\n{query}\n")
    try:
        res = graph.query(query)
        print(f"kg_doc_selector found {len(res)} matching documents")
    except Exception as e:
        print(f"Cypher execution exception: {e}")
        return []
    return [x['text'] for x in res[:3]]


class REDiarySelectorTool(BaseTool):
    name: str = "EntityRelationDiarySelector"
    description: str = (
        "Useful when you need to find highly targeted question-relevant documents (diary entries) when the question is about two entities and a relationship between them "
        "that is present in the Knowledge Graph (KG), but the KG itself does not contain enough details to provide the answer. "
        "In such case, use this tool to find such documents (diary entries) that mention the specific relation class "
        "between the specified entities. "
        "Use this tool when you can't use KnowledgeGraph tool. Only if this tool does not return results, use the Diaries tool.\n\n"
        "Full Knowledge Graph schema in Cypher syntax to help you decide whether this tool can be used or not:\n"
        f"{KG_SCHEMA}"
    )
    args_schema: Type[BaseModel] = REDiarySelectorInput

    def _run(
        self,
        entity_source: str,
        entity_source_class: str,
        entity_target: str,
        entity_target_class: str,
        rel_class: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[str]:
        """Use the tool."""
        return self.get_documents(entity_source, entity_source_class, entity_target, entity_target_class, rel_class)

    async def _arun(
        self,
        entity_source: str,
        entity_source_class: str,
        entity_target: str,
        entity_target_class: str,
        rel_class: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> List[str]:
        """Use the tool asynchronously."""
        return self.get_documents(entity_source, entity_source_class, entity_target, entity_target_class, rel_class)

    def get_documents(self, entity_source, entity_source_class, entity_target, entity_target_class, rel_class) -> List[str]:
        try:
            res = graph.query(
                RE_SELECTOR_QUERY.format(e1=entity_source, e1_class=entity_source_class,
                                         e2=entity_target, e2_class=entity_target_class,
                                         rel_class=rel_class)
            )
        except Exception(e):
            print(f"Cypher execution exception: {e}")
            return []
        return [x['text'] for x in res[:3]]