import os
import sys
import math
import spacy
import pytextrank
from pathlib import Path
from neo4j import GraphDatabase, basic_auth

from util.base_importer import BaseImporter
from util.graphdb_base import GraphDBBase


class BBCImporter(BaseImporter):
    def __init__(self, argv):
        super().__init__(command=__file__, argv=argv)
        self._database = "news"

        # load standard English NLP and NER models
        #  NORP entity = Nationalities or religious or political groups
        #  FAC entity = Buildings, airports, highways, bridges etc.
        #  GPE entity = Countries, cities, states
        self.nlp = spacy.load("en_core_web_sm")

        # CREATE DATABASE news
        self.create_indices()

        self.QUERY_IMPORT = """MERGE (t:Topic {name: $topic})
            WITH t

            UNWIND $inputs AS doc

            MERGE (n:Document {id: doc.id}) 
            SET n.title = doc.title, n.text = doc.text

            MERGE (t)-[:HAS_DOCUMENT]->(n)
            """

        self.QUERY_ENTITIES = """UNWIND $inputs AS doc

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

        self.QUERY_STORE_KEYWORDS = """UNWIND $inputs AS doc

              MATCH (n:Document)
              WHERE id(n) = doc.id

              FOREACH(entity IN doc.keywords |
                MERGE (e:Keyword {name: entity.name})
                MERGE (n)-[r:MENTIONS_KEYWORD]->(e)
                SET r.rank = entity.rank
              )
            """

    def create_indices(self):
        with self._driver.session(database=self._database) as session:
            session.run("CREATE CONSTRAINT doc ON (n:Document) ASSERT n.id IS UNIQUE")
            session.run("CREATE CONSTRAINT person ON (n:Person) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT location ON (n:Location) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT organization ON (n:Organization) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT date ON (n:Date) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT money ON (n:Money) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT number ON (n:Number) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT group ON (n:NatReligPolitGroup) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT workofart ON (n:WorkOfArt) ASSERT n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT keyword ON (n:Keyword) ASSERT n.name IS UNIQUE")

    def cleanse_entity(self, en: str):
        TO_IGNORE = ["the", "a"]
        tokenized = en.split()
        if tokenized[0].lower() in TO_IGNORE:
            en = en[len(tokenized[0]):]
        en = en.replace("\'s", "")
        return en.strip()

    def ingest_documents(self, data_path: Path):
        data = {x: list() for x in os.listdir(data_path) if os.path.isdir(os.path.join(data_path, x))}
        for topic in data.keys():
            files = os.listdir(os.path.join(data_path, topic))
            print(f"Ingesting {len(files)} files from {topic} ...")
            for file in files:
                id = topic + "_" + file[:-4]
                with open(os.path.join(data_path, topic, file), 'r') as f:
                    try:
                        lines = [x.strip() for x in f.readlines() if len(x.strip()) > 1]
                        data[topic].append({'id': id, 'title': lines[0], 'text': "\n".join(lines[1:])})
                    except UnicodeDecodeError:
                        print(f"UnicodeDecodeError for {id}")
        return data

    def enrich_by_nlp(self, documents: list):
        for doc in documents:
            processed = self.nlp(doc['title'] + ".\n\n" + doc['text'])
            for en in processed.ents:
                if en.label_ not in doc:
                    doc[en.label_] = list()
                doc[en.label_].append(self.cleanse_entity(en.text))

    def run(self, data_path: Path):
        # Ingest docments and run NLP processing
        with self._driver.session(database=self._database) as session:
            inputs = self.ingest_documents(data_path)
            for topic in inputs.keys():
                print(f"Enriching {topic} documents")
                self.enrich_by_nlp(inputs[topic])
                session.run(self.QUERY_IMPORT, topic=topic, inputs=inputs[topic])
                session.run(self.QUERY_ENTITIES, inputs=inputs[topic])

    def extract_keywords(self):
        QUERY_INGEST = """MATCH (n:Document)
              RETURN id(n) AS id, n.title AS title, n.text AS text
            """

        def cleanse_keyword(kw: str):
            TO_IGNORE = ["the", "their", "a"]
            tokenized = kw.split()
            if tokenized[0].lower() in TO_IGNORE:
                kw = kw[len(tokenized[0]):]
            return kw.lower().strip()

        # add keyword extraction to the NLP pipeline
        self.nlp.add_pipe("textrank")

        # get data for keyword extraction
        with self._driver.session(database=self._database) as session:
            documents = session.run(QUERY_INGEST).data()
        print(f"Retrieved {len(documents)} documents")

        NUM_BATCHES = 200
        batches = spacy.util.minibatch(documents, NUM_BATCHES)
        print(f"Dataset split into {math.ceil(1.0 * len(documents) / NUM_BATCHES)} batches")
        for idx, batch in enumerate(batches):
            print(f"Processing batch {idx}")
            # extract keywords
            for doc in batch:
                processed = self.nlp(doc['title'] + ".\n\n" + doc['text'])
                doc['keywords'] = [{'name': cleanse_keyword(x.text), 'rank': x.rank} for x in processed._.phrases if
                                   len(x.text) > 1][:30]

            # store back to Neo4j
            with self._driver.session(database=self._database) as session:
                print("Storing a batch of keywords to Neo4j")
                session.run(self.QUERY_STORE_KEYWORDS, inputs=batch)


if __name__ == "__main__":
    importer = BBCImporter(argv=sys.argv[1:])
    base_path = importer.source_dataset_path

    if not base_path:
        print("source path directory is mandatory. Setting it to default.")
        base_path = "../../data/bbc/"

    base_path = Path(base_path)

    # Ingest articles & run NLP processing
    importer.run(base_path)

    # for each article, extract keywords and key-phrases (enrichment of the KG created in previous step)
    importer.extract_keywords()