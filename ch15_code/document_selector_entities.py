from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool


class KGDiaryToolInput(BaseModel):
    entity: str = Field(description="movie or a person mentioned in the question")
    entity_type: str = Field(
        description="type of the entity. Available options are 'movie' or 'person'"
    )


class KGDiaryTool(BaseTool):
    name = "KnowledgeGraphAndDiaries"
    description = (
        "useful for when you need to answer questions about various actors or movies"
    )
    args_schema: Type[BaseModel] = KGDiaryToolInput

    def _run(
        self,
        entity: str,
        entity_type: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return get_information(entity, entity_type)

    async def _arun(
        self,
        entity: str,
        entity_type: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return get_information(entity, entity_type)