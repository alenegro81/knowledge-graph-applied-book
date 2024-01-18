import os
import time
import json
from openai import AzureOpenAI

from neo4j import GraphDatabase, basic_auth

NEO4J_DB = "rac2"

# Azure OpenAI
api_key = "d28eb2ef49754a3796f970de6fb8809a"
#openai.api_type = "azure"
api_base = "https://ga-sandbox.openai.azure.com"
api_version = "2023-12-01-preview"


if __name__ == "__main__":
    client = AzureOpenAI(
        # https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#rest-api-versioning
        api_version=api_version,
        azure_endpoint=api_base,
        api_key=api_key
        #api_key=os.environ['OPENAI_API_KEY']
    )