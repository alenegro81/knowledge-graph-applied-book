import sys
import logging

from neo4j.exceptions import ClientError as Neo4jClientError

from util.base_importer import BaseImporter

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


class HPOImporter(BaseImporter):

    def __init__(self, argv):
        super().__init__(command=__file__, argv=argv)
        self._database = "hpo"
        with self._driver.session() as session:
            # Listing 16
            session.run(f"CREATE DATABASE {self._database} IF NOT EXISTS")

    def set_constraints(self):
        # Listing 17
        queries = ["CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;",
                   "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Resource) REQUIRE (n.id) IS UNIQUE;",
                   "CREATE INDEX disease_id IF NOT EXISTS FOR (n:HpoDisease) ON (n.id);",
                   "CREATE INDEX phenotype_id IF NOT EXISTS FOR (n:HpoPhenotype) ON (n.id);"]
        with self._driver.session(database=self._database) as session:
            for q in queries:
                try:
                    session.run(q)
                except Neo4jClientError as e:
                    # ignore if we already have the rule in place
                    if e.code != "Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists":
                        raise e

    def check_neo_semantics(self):
        query = 'SHOW PROCEDURES YIELD name WHERE name ="n10s.graphconfig.init"'
        with self._driver.session(database=self._database) as session:
            r = session.run(query)
            if len(r.data()) == 0:
                raise RuntimeError(
                    "Can not find `n10s.graphconfig.init`.Please make sure that Neosemantics is installed.\n"
                    "https://neo4j.com/labs/neosemantics/installation/")

    def initialize_neo_semantics(self):
        # check if the RDF data is already imported
        test_query = "MATCH (n:Resource) RETURN n"
        with self._driver.session(database=self._database) as session:
            r = session.run(test_query)
            if len(r.data()) == 0:
                # Listing 18
                queries = ["CALL n10s.graphconfig.init();",
                           "CALL n10s.graphconfig.set({ handleVocabUris: 'IGNORE' });",
                           "CALL n10s.graphconfig.set({ applyNeo4jNaming: True });"]

                with self._driver.session(database=self._database) as session:
                    for q in queries:
                        session.run(q)
                       

    def load_HPO_ontology(self):
        # Listing 19
        query = """
                CALL n10s.rdf.import.fetch("http://purl.obolibrary.org/obo/hp.owl","RDF/XML");
                """
        with self._driver.session(database=self._database) as session:
            session.run(query)

    def label_HPO_entities(self):
        # Listing 20
        query = """
                MATCH (n:Resource) 
                WHERE n.uri STARTS WITH "http://purl.obolibrary.org/obo/HP" 
                SET n:HpoPhenotype, 
                    n.id = coalesce(n.id, replace(apoc.text.replace(n.uri,'(.*)obo/',''),'_', ':'));
                """
        with self._driver.session(database=self._database) as session:
            session.run(query)

    def create_disease_entities(self):
        # Listing 22
        query = """
                LOAD CSV FROM 'https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa' AS row 
                FIELDTERMINATOR '\t'
                WITH row
                SKIP 5 
                MERGE (dis:Resource:HpoDisease {id: row[0]}) 
                ON CREATE SET dis.label = row[1]; 
                """

        with self._driver.session(database=self._database) as session:
            session.run(query)

    def create_rels_features_diseases(self):
        # Listing 23
        query = """
                LOAD CSV FROM 'https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa' AS row
                FIELDTERMINATOR '\t'
                WITH row
                SKIP 5
                MATCH (dis:HpoDisease)
                WHERE dis.id = row[0]
                MATCH (phe:HpoPhenotype)
                WHERE phe.id = row[3]
                MERGE (dis)-[:HAS_PHENOTYPIC_FEATURE]->(phe)
                """

        with self._driver.session(database=self._database) as session:
            session.run(query)

    def add_base_properties_to_rels(self):
        # Listing 25
        query = """
                LOAD CSV FROM 'https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/phenotype.hpoa' AS row 
                FIELDTERMINATOR '\t' 
                WITH row 
                SKIP 5 
                MATCH (dis:HpoDisease)-[rel:HAS_PHENOTYPIC_FEATURE]->(phe:HpoPhenotype)
                WHERE phe.id = row[3] and dis.id = row[0] 
                FOREACH(ignoreMe IN CASE WHEN row[4] is not null THEN [1] ELSE [] END| 
                    SET rel.source = row[4]) 
                FOREACH(ignoreMe IN CASE WHEN row[5] is not null THEN [1] ELSE [] END| 
                    SET rel.evidence = row[5]) 
                FOREACH(ignoreMe IN CASE WHEN row[6] is not null THEN [1] ELSE [] END| 
                    SET rel.onset = row[6]) 
                FOREACH(ignoreMe IN CASE WHEN row[7] is not null THEN [1] ELSE [] END| 
                    SET rel.frequency = row[7]) 
                FOREACH(ignoreMe IN CASE WHEN row[8] is not null THEN [1] ELSE [] END| 
                    SET rel.sex = row[8]) 
                FOREACH(ignoreMe IN CASE WHEN row[9] is not null THEN [1] ELSE [] END| 
                    SET rel.modifier = row[9]) 
                FOREACH(ignoreMe IN CASE WHEN row[10] is not null THEN [1] ELSE [] END| 
                    SET rel.aspect = row[10])
                FOREACH(ignoreMe IN CASE WHEN row[11] is not null THEN [1] ELSE [] END| 
                    SET rel.biocuration = row[11])
                """

        with self._driver.session(database=self._database) as session:
            session.run(query)

    def enrich_with_descriptive_properties(self):
        # Listing 26
        query = """
                CALL apoc.periodic.iterate(
                    "MATCH (dis:HpoDisease)-[rel:HAS_PHENOTYPIC_FEATURE]->(phe:HpoPhenotype) RETURN rel",
                    "SET rel.createdBy = apoc.text.regexGroups(rel.biocuration, 'HPO:(\\w+)\\[')[0][1],
                    rel.creationDate = apoc.text.regexGroups(rel.biocuration, '\\[(\\d{4}-\\d{2}-\\d{2})\\]')[0][1],
                    rel.aspectName = 
                    CASE  
                        WHEN rel.aspect = 'P' THEN 'Phenotypic abnormality' 
                        WHEN rel.aspect = 'I' THEN 'Inheritance' 
                    END, 
                    rel.aspectDescription = 
                    CASE 
                        WHEN rel.aspect = 'P' THEN 'Terms with the P aspect are located in the Phenotypic abnormality subontology' 
                        WHEN rel.aspect = 'I' THEN 'Terms with the I aspect are from the Inheritance subontology' 
                    END, 
                    rel.evidenceName = 
                    CASE  
                        WHEN rel.evidence = 'IEA' THEN 'Inferred from electronic annotation' 
                        WHEN rel.evidence = 'PCS' THEN 'Published clinical study' 
                        WHEN rel.evidence = 'TAS' THEN 'Traceable author statement' 
                    END, 
                    rel.evidenceDescription = 
                    CASE 
                        WHEN rel.evidence = 'IEA' THEN 'Annotations extracted by parsing the Clinical Features sections of the Online Mendelian Inheritance in Man resource are assigned the evidence code IEA.' 
                        WHEN rel.evidence = 'PCS' THEN 'PCS is used for information extracted from articles in the medical literature. Generally, annotations of this type will include the pubmed id of the published study in the DB_Reference field.' 
                        WHEN rel.evidence = 'TAS' THEN 'TAS is used for information gleaned from knowledge bases such as OMIM or Orphanet that have derived the information from a published source.' 
                    END, 
                    rel.url = 
                    CASE 
                        WHEN rel.source STARTS WITH 'PMID:' THEN 'https://pubmed.ncbi.nlm.nih.gov/' + apoc.text.replace(rel.source, '(.*)PMID:', '') 
                        WHEN rel.source STARTS WITH 'OMIM:' THEN 'https://omim.org/entry/' + apoc.text.replace(rel.source, '(.*)OMIM:', '') 
                    END",
                {batchSize: 1000})
                """

        with self._driver.session(database=self._database) as session:
            session.run(query)
    
    def remove_unused_node(self):
        # Listing 27
        query = """
                CALL apoc.periodic.iterate(
                    "MATCH (n:Resource) RETURN id(n) as node_id",
                    "MATCH (n)
                     WHERE id(n) = node_id AND
                           NOT 'HpoPhenotype' in labels(n) AND
                           NOT 'HpoDisease' in labels(n)
                     DETACH DELETE n",
                     {batchSize:10000})
                YIELD batches, total return batches, total
                """

        with self._driver.session(database=self._database) as session:
            session.run(query)


if __name__ == '__main__':
    importing = HPOImporter(argv=sys.argv[1:])
    logging.info('Setting Constraints')
    importing.set_constraints()
    logging.info('Initializing Neosemantics')
    importing.check_neo_semantics()
    importing.initialize_neo_semantics()
    logging.info('Loading HPO Ontology')
    importing.load_HPO_ontology()
    logging.info('Loading HPO Entities')
    importing.label_HPO_entities()
    logging.info('Creating Disease Entities')
    importing.create_disease_entities()
    logging.info('Creating Phenotype Relationships')
    importing.create_rels_features_diseases()
    logging.info('Base Relationship Enriching')
    importing.add_base_properties_to_rels()
    logging.info('Descriptive Relationship Enriching')
    importing.enrich_with_descriptive_properties()
    logging.info('Cleaning the Knowledge Graph...')
    importing.remove_unused_node()
