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


def openai_query_azure(client, model, query):
    messages = [{"role": "system", "content": "Answer the questions the best you can."},
                {"role": "user", "content": query}
                ]
    t_start = time.time()
    response = client.chat.completions.create(model=model, messages=messages, temperature=0, max_tokens=2000)
                                        #top_p=1.0, frequency_penalty=0.0, presence_penalty=0.0 #, best_of=3
                                        #)
    #print(response.choices[0].message.content)
    print(f"Time: {round(time.time() - t_start, 1)} sec")
    return response.choices[0].message.content


if __name__ == "__main__":
    client = AzureOpenAI(
        # https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#rest-api-versioning
        api_version=api_version,
        azure_endpoint=api_base,
        api_key=api_key
        #api_key=os.environ['OPENAI_API_KEY']
    )

    #question = "What did Ernest O. Lawrence and Niels Bohr talk about?"
    #question = "How is Ernest O. Lawrence related to University of California?"
    #question = "How is Harvard related to Johns Hopkins University?"
    question = "Who are the top influencers of cyclotron funding in 1930s?"
    #question = "What did August Krogh say about Lawrence Irving?"
    #question = "How was Dorothy M. Wrinch perceived among her colleagues?"
    model = "gpt-35-turbo"
    #model = "gpt-4"
    result = openai_query_azure(client, model, question)

    print(result)