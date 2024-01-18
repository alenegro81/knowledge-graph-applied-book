
NEO4J_DB = "news"

def enrich_wikidata():
    import time
    import json
    import requests
    from neo4j import GraphDatabase, basic_auth

    QUERY_GET_INPUTS = """
    USE news
    MATCH (n:Document)-[:MENTIONS_ORGANIZATION]->(e:Organization)
    WITH e, count(*) AS c
    WHERE c > 4
    RETURN id(e) AS id, e.name AS name
    """

    QUERY_STORE_RESULTS = """
    USE news
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

    def get_wikidata(entity: str):
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
        """ % entity

        URL = f"https://query.wikidata.org/bigdata/namespace/wdq/sparql?query={SPARQL}"

        try:
            response = requests.get(URL, params={'format': "json"})
            if response.status_code == 429:
                print("Too many requests")
            parsed = json.loads(response.content)
            time.sleep(1) # to avoid exception about too many requests
        except json.decoder.JSONDecodeError as e:
            print(f"JSONDecodeError: Couldn't process entity {entity}: {e}")
            return dict()
        except Exception as e:
            print(f"Couldn't process entity {entity}: {e}")
            return dict()

        results = parsed['results']['bindings']

        final_res = {'name': results[0]['orgLabel']['value'],
                     'wikidata_url': results[0]['org']['value'],
                     'wikidata_id': results[0]['org']['value'].split("/")[-1].strip(),
                     'description': results[0]['desc']['value'],
                     'subsidiary': list(set(results[0]['subsidiaries']['value'].split(";"))),
                     'member_of': list(set(results[0]['members']['value'].split(";"))),
                     'industry': list(set(results[0]['industries']['value'].split(";"))),
                     } if len(results) > 0 else dict()

        return final_res

    # Initialise Neo4j driver
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=basic_auth('neo4j', 'neo'))

    # Run enrichment
    with driver.session(database=NEO4J_DB) as session:
        # Get entities to enrich
        entities = session.run(QUERY_GET_INPUTS).data()
        print(f"Retrieved {len(entities)} entities")

        print("Retrieving wikidata info for entity:")
        for en in entities:
            print(en['name'])
            wiki = get_wikidata(en['name'])
            if len(wiki) == 0:
                # print("  Nothing found.")
                continue
            wiki['id'] = en['id']
            session.run(QUERY_STORE_RESULTS, input=wiki)
            print("  STORED!")


def enrich_owned_by():
    import json
    import requests
    import time
    import math
    import spacy
    from neo4j import GraphDatabase, basic_auth

    QUERY_GET_INPUTS = """MATCH (e:Organization)
    WHERE EXISTS(e.wikidata_id)
    RETURN id(e) AS id, e.name AS name, e.wikidata_id AS wikidata_id
    """

    QUERY_STORE_RESULTS = """UNWIND $inputs AS input
    MATCH (n)
    WHERE id(n) = input.id

    FOREACH(entity IN input.owned_by_org |
        MERGE (e:Organization {name: entity})
        SET e:Owner
        MERGE (n)-[:OWNED_BY_ORG]->(e)
    )
    
    FOREACH(entity IN input.owned_by_per |
        MERGE (e:Person {name: entity})
        SET e:Owner
        MERGE (n)-[:OWNED_BY_PER]->(e)
    )
    """

    def query_wikidata(query: str):
        URL = f"https://query.wikidata.org/bigdata/namespace/wdq/sparql?query={query}"
        response = requests.get(URL, params={'format': "json"})
        parsed = json.loads(response.content)
        results = parsed['results']['bindings']
        return results

    def get_owners(entities: list):
        """
        Retrieve wikidata IDs of owners for each entity
        :param entities: list of entities represented as dictionaries
        :return: dictionary {<entity_node_id>: list(owners)}
        """
        ents = " ".join([f"(wd:{x['wikidata_id']})" for x in entities])
        SPARQL = """
        SELECT ?org ?owned_by
        WHERE { VALUES(?org) {%s} .
                ?org wdt:P127 ?owned_by .
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """ % ents

        results = query_wikidata(SPARQL)
        final_res = dict()
        for r in results:
            org_id = r['org']['value'].split("/")[-1].strip()
            node_id = [x['id'] for x in entities if x['wikidata_id'] == org_id][0]
            if node_id not in final_res:
                final_res[node_id] = list()
            final_res[node_id].append(r['owned_by']['value'].split("/")[-1].strip())

        return final_res


    def disambiguate_owners(entities: dict):
        # verify owner entity type (Organization or Person)
        ents = " ".join([f"(wd:{owner})" for x in entities.values() for owner in x])
        SPARQL = """
        SELECT ?ent ?entLabel ?instance_of
        WHERE {
            VALUES(?ent) {%s} .
            OPTIONAL {?ent wdt:P31 ?instance_of . }
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """ % ents

        results = query_wikidata(SPARQL)

        dict_owners = dict()
        for r in results:
            ent = r['ent']['value'].split("/")[-1]
            inst = r['instance_of']['value'].split("/")[-1] if 'instance_of' in r else None
            dict_owners[ent] = {'name': r['entLabel']['value'].strip(),
                                'type': "person" if inst == "Q5" else "organization"
                                }

        final_res = list()
        for en, owners in entities.items():
            final_res.append({'id': en, 'owned_by_org': list(), 'owned_by_per': list()})
            for ow in owners:
                label = 'owned_by_per' if dict_owners[ow]['type'] == "person" else 'owned_by_org'
                final_res[-1][label].append(dict_owners[ow]['name'])

        return final_res

    #print(disambiguate_owners(["wd:Q67", "wd:Q312556"]))

    # Initialise Neo4j driver
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=basic_auth('neo4j', 'neo'))

    # Get entities to enrich
    with driver.session(database=NEO4J_DB) as session:
        entities = session.run(QUERY_GET_INPUTS).data()
        print(f"Retrieved {len(entities)} entities")

        # run in batches
        NUM_BATCHES = 20
        batches = spacy.util.minibatch(entities, NUM_BATCHES)
        print(f"Entities split into {math.ceil(1.0 * len(entities) / NUM_BATCHES)} batches")
        for idx, batch in enumerate(batches):
            print(f"Processing batch {idx}")
            owners = get_owners(entities)
            time.sleep(1)
            results = disambiguate_owners(owners)
            time.sleep(1)
            session.run(QUERY_STORE_RESULTS, inputs=results)



if __name__ == "__main__":

    enrich_wikidata()

    enrich_owned_by()

