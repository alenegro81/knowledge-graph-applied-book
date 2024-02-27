import sys
import json
import time
import requests

from util.base_importer import BaseImporter


def query_wikidata_entity(query: str, entity: str):
    try:
        URL = f"https://query.wikidata.org/bigdata/namespace/wdq/sparql?query={query % entity}"
        response = requests.get(URL, params={'format': "json"})
        if response.status_code == 429:
            print("Too many requests")
        parsed = json.loads(response.content)
    except json.decoder.JSONDecodeError as e:
        print(f"JSONDecodeError: Couldn't process entity {entity}: {e}")
        return dict()
    except Exception as e:
        print(f"Couldn't process entity {entity}: {e}")
        return dict()
    results = parsed['results']['bindings']
    return results


class OrgEnricher(BaseImporter):
    def __init__(self, argv):
        super().__init__(command=__file__, argv=argv)
        self._database = "news"

        self.QUERY_GET_INPUTS = """
        MATCH (n:Document)-[:MENTIONS_ORGANIZATION]->(e:Organization)
        WITH e, count(*) AS c
        WHERE c > 4
        RETURN id(e) AS id, e.name AS name
        """

        self.QUERY_STORE_RESULTS = """
        MATCH (n)
        WHERE id(n) = $input.id
        SET n.description = $input.description,
        n.wikidata_id = $input.wikidata_id,
        n.wikidata_url = $input.wikidata_url
    
        WITH n 
    
        FOREACH(entity IN $input.subsidiary |
            MERGE (e:Organization {name: entity})
            MERGE (n)-[:HAS_SUBSIDIARY]->(e)
        )
    
        FOREACH(entity IN $input.member_of |
            MERGE (e:Organization {name: entity})
            MERGE (n)-[:MEMBER_OF]->(e)
        )
    
        FOREACH(entity IN $input.industry |
            MERGE (e:Industry {name: entity})
            MERGE (n)-[:IN_INDUSTRY]->(e)
        )
        """

    def get_wikidata(self, entity: str):
        SPARQL = """
        SELECT ?org ?orgLabel ?desc  (group_concat(distinct ?subsidiaryLabel;separator=";") as ?subsidiaries)  (group_concat(distinct ?member_ofLabel;separator=";") as ?members)  (group_concat(distinct ?industryLabel;separator=";") as $industries)
        WHERE {{?org    wdt:P31 wd:Q4830453 .}
         UNION
         {?org    wdt:P31 wd:Q43229 .}
         ?org      rdfs:label '%s'@en .
         ?org schema:description ?desc .
         OPTIONAL {?org        wdt:P17 ?country . }
         OPTIONAL {?org        wdt:P355 ?subsidiary . }
         OPTIONAL {?org        wdt:P452 ?industry . }
         OPTIONAL {?org        wdt:P1813 ?short_name . }
         OPTIONAL {?org        wdt:P463 ?member_of . }
         FILTER(LANG(?desc) = "en")
         SERVICE wikibase:label { 
           bd:serviceParam wikibase:language "en".
           ?org rdfs:label ?orgLabel.
           ?subsidiary rdfs:label ?subsidiaryLabel.
           ?industry rdfs:label ?industryLabel.
           ?member_of rdfs:label ?member_ofLabel.
         }
        }
        GROUP BY ?org ?orgLabel ?desc
        """

        results = query_wikidata_entity(SPARQL, entity)

        final_res = {'name': results[0]['orgLabel']['value'],
                     'wikidata_url': results[0]['org']['value'],
                     'wikidata_id': results[0]['org']['value'].split("/")[-1].strip(),
                     'description': results[0]['desc']['value'],
                     'subsidiary': list(set(results[0]['subsidiaries']['value'].split(";"))),
                     'member_of': list(set(results[0]['members']['value'].split(";"))),
                     'industry': list(set(results[0]['industries']['value'].split(";"))),
                     } if len(results) > 0 else dict()

        return final_res

    def run(self):
        # Run enrichment
        with self._driver.session(database=self._database) as session:
            # Get entities to enrich
            entities = session.run(self.QUERY_GET_INPUTS).data()
            print(f"Retrieved {len(entities)} entities")

            print("Retrieving wikidata info for entity:")
            for en in entities:
                print(en['name'])
                wiki = self.get_wikidata(en['name'])
                time.sleep(1)  # to avoid exception about too many requests
                if len(wiki) == 0:
                    # print("  Nothing found.")
                    continue
                wiki['id'] = en['id']
                session.run(self.QUERY_STORE_RESULTS, input=wiki)
                print("  STORED!")


if __name__ == "__main__":
    enricher = OrgEnricher(argv=sys.argv[1:])
    enricher.run()

