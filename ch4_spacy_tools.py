
# Spacy:
#  NORP entity = Nationalities or religious or political groups
#  FAC entity = Buildings, airports, highways, bridges etc.
#  GPE entity = Countries, cities, states

def visualise_dependency(text):
    # https://spacy.io/usage/visualizers
    import spacy
    from spacy import displacy

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    print(doc)
    displacy.serve(doc, style="dep") #, options={'compact': True})


def basic_ner(text):
    import spacy
    from spacy import displacy

    # load standard English NLP and NER models
    # start with downloading the models by running this command: `python -m spacy download en_core_web_md`
    #nlp = spacy.load("en_core_web_sm")
    nlp = spacy.load("en_core_web_md")

    doc = nlp(text)

    print("\n".join([f"{en.text}\t{en.label_}\t-\t{spacy.explain(en.label_)}" for en in doc.ents]))
    #displacy.serve(doc, style="ent")  # , page=True, options={"ents": ["PERSON", "ORG"]})


def regex_ner_token_matcher(text):
    import spacy
    from spacy.matcher import Matcher

    nlp = spacy.load("en_core_web_sm")

    matcher = Matcher(nlp.vocab)
    patterns = [[{"LEMMA": "writer"}], [{"LEMMA": "singer"}]]
    matcher.add("TITLE", patterns)

    doc = nlp(text)
    print("\n".join([f"{en.text}\t{en.label_}\t-\t{spacy.explain(en.label_)}" for en in doc.ents]))

    matches = matcher(doc)
    for match_id, start, end in matches:
        string_id = nlp.vocab.strings[match_id]  # Get string representation
        span = doc[start:end]  # The matched span
        print(match_id, string_id, start, end, span.text)

def regex_ner(text):
    import spacy
    from spacy import displacy

    # load standard English NLP and NER models
    nlp = spacy.load("en_core_web_sm")

    # add entity ruler to the pipeline
    ruler = nlp.add_pipe("entity_ruler")

    # define NER dictionary patterns
    patterns = [{"pattern": [{"LEMMA": "writer"}], "label": "TITLE"}]
    patterns.append({"pattern": [{"LOWER": "chief"}, {"POS": "PROPN"}, {"POS": "PROPN", "OP": "?"}, {"LOWER": "officer"}], "label": "TITLE"}) #exercise
    patterns.append({"pattern": [{"LOWER": "chief"}, {"POS": "NOUN"}, {"POS": "NOUN", "OP": "?"}, {"LOWER": "officer"}], "label": "TITLE"}) #exercise
    patterns.append({"pattern": [{"TEXT": {"REGEX": "C[A-Z]O"}}], "label": "TITLE"}) #exercise
    ruler.add_patterns(patterns)

    doc = nlp(text)

    print("\n".join([f"{en.text}\t{en.label_}\t-\t{spacy.explain(en.label_)}" for en in doc.ents]))
    #displacy.serve(doc, style="dep") #, port=1111)


def ingest_news():
    # CREATE DATABASE news
    # CREATE CONSTRAINT doc ON (n:Document) ASSERT n.id IS UNIQUE
    # CREATE CONSTRAINT person ON (n:Person) ASSERT n.name IS UNIQUE
    # CREATE CONSTRAINT keyword ON (n:Keyword) ASSERT n.name IS UNIQUE
    # pip install pytextrank
    import os
    import spacy
    from neo4j import GraphDatabase, basic_auth

    PATH_DATA = "data/bbc-2"

    QUERY_IMPORT = """USE news
    MERGE (t:Topic {name: $topic})
    WITH t
    
    UNWIND $inputs AS doc
    
    MERGE (n:Document {id: doc.id}) 
    SET n.title = doc.title, n.text = doc.text
    
    MERGE (t)-[:HAS_DOCUMENT]->(n)
    """

    QUERY_ENTITIES = """USE news
    UNWIND $inputs AS doc
    
    MATCH (n:Document {id: doc.id})
    
    FOREACH(entity IN doc.PERSON |
      MERGE (e:Person {name: entity})
      MERGE (n)-[:MENTIONS_PERSON]->(e)
    )
    
    FOREACH(entity IN doc.ORG |
      MERGE (e:Organization {name: entity})
      MERGE (n)-[:MENTIONS_ORGANIZATION]->(e)
    )
    
    FOREACH(entity IN doc.GPE |
      MERGE (e:Location {name: entity})
      MERGE (n)-[:MENTIONS_LOCATION]->(e)
    )
    
    FOREACH(entity IN doc.DATE |
      MERGE (e:Date {name: toLower(entity)})
      MERGE (n)-[:MENTIONS_DATE]->(e)
    )
    
    FOREACH(entity IN doc.MONEY |
      MERGE (e:Money {name: entity})
      MERGE (n)-[:MENTIONS_MONEY]->(e)
    )
    
    FOREACH(entity IN doc.CARDINAL |
      MERGE (e:Number {name: entity})
      MERGE (n)-[:MENTIONS_NUMER]->(e)
    )
    
    FOREACH(entity IN doc.NORP |
      MERGE (e:NatReligPolitGroup {name: entity})
      MERGE (n)-[:MENTIONS_GROUP]->(e)
    )
    
    FOREACH(entity IN doc.WORK_OF_ART |
      MERGE (e:WorkOfArt {name: entity})
      MERGE (n)-[:MENTIONS_WORK_OF_ART]->(e)
    )
    """

    def cleanse_entity(en: str):
        TO_IGNORE = ["the", "a"]
        tokenized = en.split()
        if tokenized[0].lower() in TO_IGNORE:
            en = en[len(tokenized[0]):]
        en = en.replace("\'s", "")
        return en.strip()

    def ingest_documents(path: str):
        data = {x: list() for x in os.listdir(PATH_DATA) if os.path.isdir(os.path.join(PATH_DATA, x))}
        for topic in data.keys():
            files = os.listdir(os.path.join(PATH_DATA, topic))
            print(f"Ingesting {len(files)} files from {topic} ...")
            for file in files:
                id = topic + "_" + file[:-4]
                with open(os.path.join(PATH_DATA, topic, file), 'r') as f:
                    try:
                        lines = [x.strip() for x in f.readlines() if len(x.strip()) > 1]
                        data[topic].append({'id': id, 'title': lines[0], 'text': "\n".join(lines[1:])})
                    except UnicodeDecodeError:
                        print(f"UnicodeDecodeError for {id}")
        return data

    ########################### TO DO ! Replace ingest_documents() with this one ... ###########################
    def ingest_documents_v2():
        from sklearn.datasets import fetch_20newsgroups

        docs = fetch_20newsgroups(subset='all', remove=('headers', 'footers', 'quotes'))['data']

    def enrich_by_nlp(documents: list):
        # load standard English NLP and NER models
        nlp = spacy.load("en_core_web_sm")

        for doc in documents:
            processed = nlp(doc['title'] + ".\n\n" + doc['text'])
            for en in processed.ents:
                if en.label_ not in doc:
                    doc[en.label_] = list()
                doc[en.label_].append(cleanse_entity(en.text))

    # Initialise Neo4j driver
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=basic_auth('neo4j', 'neo'))

    with driver.session() as session:
        inputs = ingest_documents(PATH_DATA)
        for topic in inputs.keys():
            print(f"Enriching {topic} documents")
            enrich_by_nlp(inputs[topic])
            session.run(QUERY_IMPORT, topic=topic, inputs=inputs[topic])
            session.run(QUERY_ENTITIES, inputs=inputs[topic])

    driver.close()


def extract_keywords():
    import spacy
    import pytextrank
    import math
    from neo4j import GraphDatabase, basic_auth

    NUM_BATCHES = 200

    QUERY_INGEST = """
      USE news
      MATCH (n:Document)
      RETURN id(n) AS id, n.title AS title, n.text AS text
    """

    QUERY_STORE_KEYWORDS = """
      USE news
    
      UNWIND $inputs AS doc
    
      MATCH (n:Document)
      WHERE id(n) = doc.id
        
      FOREACH(entity IN doc.keywords |
        MERGE (e:Keyword {name: entity.name})
        MERGE (n)-[r:MENTIONS_KEYWORD]->(e)
        SET r.rank = entity.rank
      )
    """

    def cleanse_keyword(kw: str):
        TO_IGNORE = ["the", "their", "a"]
        tokenized = kw.split()
        if tokenized[0].lower() in TO_IGNORE:
            kw = kw[len(tokenized[0]):]
        return kw.lower().strip()

    # Initialise Neo4j driver
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=basic_auth('neo4j', 'neo'))

    # load standard English NLP and NER models
    nlp = spacy.load("en_core_web_sm")

    # add keyword extraction to the NLP pipeline
    nlp.add_pipe("textrank")

    # get data for keyword extraction
    with driver.session() as session:
        documents = session.run(QUERY_INGEST).data()
    print(f"Retrieved {len(documents)} documents")

    batches = spacy.util.minibatch(documents, NUM_BATCHES)
    print(f"Dataset split into {math.ceil(1.0 * len(documents) / NUM_BATCHES)} batches")
    for idx, batch in enumerate(batches):
        print(f"Processing batch {idx}")
        # extract keywords
        for doc in batch:
            processed = nlp(doc['title'] + ".\n\n" + doc['text'])
            doc['keywords'] = [{'name': cleanse_keyword(x.text), 'rank': x.rank} for x in processed._.phrases if
                                   len(x.text) > 1][:30]

        # store back to Neo4j
        with driver.session() as session:
            print("Storing a batch of keywords to Neo4j")
            session.run(QUERY_STORE_KEYWORDS, inputs=batch)




if __name__ == "__main__":
    text = "Jane Austen, the Victorian era writer, works nowadays for Google."

    #visualise_dependency(text)
    basic_ner(text)

    #text = "Jane Austen, the Victorian era writer and Chief data officer and CEO, works nowadays for Google."
    #regex_ner(text)

    #ingest_news()

    #extract_keywords()