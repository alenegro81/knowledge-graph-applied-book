
KG_SCHEMA = """Nodes:
(:Person {{name: str, titles: [], pagerank: float, betweenness: float}})
(:Organization {{name: str}})
(:Occupation {{name: str, type: str}})


Relationships:
(:Person)-[:WORKS_FOR]->(:Organization)
(:Person)-[:WORKS_WITH]->(:Person)
(:Person)-[:TALKED_WITH {{sentiment (one of positive, neutral, negative), conversation_type: str}}]->(:Person)
(:Person)-[:TALKED_ABOUT {{sentiment (one of positive, neutral, negative)}}]->(:Person)
(:Person)-[:WORKS_ON]->(:Occupation)
(:Person)-[:HAS_TITLE]->(:Title)
(:Occupation)-[:SIMILAR_OCCUPATION]->(:Occupation)
(:Organization)-[:SIMILAR_ORGANIZATION]->(:Organization)
"""