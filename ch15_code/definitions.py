
KG_SCHEMA = """(:Person)-[:WORKS_FOR]->(:Organization)
(:Person)-[:WORKS_WITH]->(:Person)
(:Person)-[:TALKED_WITH]->(:Person)
(:Person)-[:TALKED_ABOUT]->(:Person)
(:Person)-[:WORKS_ON]->(:Occupation)
(:Person)-[:HAS_TITLE]->(:Title)
(:Occupation)-[:SIMILAR_OCCUPATION]->(:Occupation)
(:Organization)-[:SIMILAR_ORGANNIZATION]->(:Organization)
"""