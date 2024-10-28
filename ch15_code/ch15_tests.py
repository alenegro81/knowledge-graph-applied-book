import os
import time
import json
from pprint import pprint

from openai import AzureOpenAI
from langchain import hub

from neo4j import GraphDatabase, basic_auth

NEO4J_DB = "rac2"

# Azure OpenAI
api_key = "d28eb2ef49754a3796f970de6fb8809a"
#openai.api_type = "azure"
api_base = "https://ga-sandbox.openai.azure.com"
api_version = "2023-12-01-preview"





if __name__ == "__main__":
    #question = "What did Ernest O. Lawrence and Niels Bohr talk about?"
    #question = "How is Ernest O. Lawrence related to University of California?"
    #question = "How is Harvard related to Johns Hopkins University?"
    question = "Who are the top influencers of cyclotron funding in 1930s?"
    #question = "What did August Krogh say about Lawrence Irving?"
    #question = "How was Dorothy M. Wrinch perceived among her colleagues?"

    model = "gpt-35-turbo"
    #model = "gpt-4"
    #result = openai_query_azure(client, model, question)
    #print(result)

    #prompt = hub.pull("hwchase17/structured-chat-agent")
    prompt = hub.pull("hwchase17/react")
    print(prompt.invoke({'tool_names': "<tool_names>", 'tools': ["<tools>"], 'input': "<input>", 'agent_scratchpad': ["<scratchpad"]}).to_string())
    for msg in prompt.messages:
        pprint(msg)

