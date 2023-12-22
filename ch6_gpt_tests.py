import json
import os
import time
import openai

openai.api_key = "d28eb2ef49754a3796f970de6fb8809a"

### for Azure
openai.api_type = "azure"
openai.api_base = "https://ga-sandbox.openai.azure.com"
openai.api_version = "2023-05-15"

prompt_v1 = """
Given a prompt, identify as many entities and relations among them as possible and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, 
ENTITY 2, ENTITY 2 TYPE]. 
The relations are directed, so the order matters.

Example:
prompt: J.R.Smith (Prof. Phys.) is employed by MIT and mentioned another scientist, Mary Hodge, who works on cyclotron research.
###output:
["J. R. Smith", "person", "has title", "Prof. of Physics", "title"]
["J. R. Smith", "person", "works for", "MIT", "organization"]
["J. R. Smith", "person", "talked about", "Mary", "person"] 
["Mary", "person", "works on", "cyclotron", "occupation"]

prompt: {0}
###output:
"""


prompt_v2 = """
Given a prompt, identify as many entities and relations among them as possible and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, ENTITY 2, ENTITY 2 TYPE]. 
The relations are directed, so the order matters.

Entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, interests, occupation).
Top relations of interest: "works for", "works with", "student of" (link students with their teachers/advisors), "talked about" (a person talking about another person), "talked with" (a person talking with another person), "works on" (assignment of persons to their occupation, work, specialisation, research discipline, interests etc.).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R.".
Note that organizations (universities, their departments) are often shortened, for example: "University of California" is written as "U. of Cal." or just "U. Cal.", "Department of Physics" is written as "Dept. Phys." etc.

Example:
prompt: J.R.Smith (Prof. Phys.) is employed by MIT and mentioned another scientist, Mary Hodge, who works on cyclotron research.
###output:
["J. R. Smith", "person", "has title", "Professor of Physics", "title"]
["J. R. Smith", "person", "works for", "MIT", "organization"]
["J. R. Smith", "person", "talked about", "Mary", "person"] 
["Mary", "person", "works on", "cyclotron", "occupation"]

prompt: {0}
###output:
"""


prompt_v3 = """
Given a prompt which represents diary entry of Warren Weaver, identify as many entities and relations among them as possible and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, ENTITY 2, ENTITY 2 TYPE]. 
The relations are directed, so the order matters.
Entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, interests, occupation), technology.
Top relations of interest: "works for", "works with", "student of" (i.e. link students with their teachers/advisors), "talked about" (i.e. a person talking about another person), "talked with" (i.e. a person talking with another person), "works on" (i.e. assignment of persons to their occupation, work, specialisation, research discipline, interests, technology etc.).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R.".
Note that organizations (universities, their departments) are often shortened, for example: "University of California" is written as "U. of Cal." or just "U. Cal.", "Department of Physics" is written as "Dept. Phys." etc.

Example:
prompt: J.R.Smith, Prof. Phys. is employed by MIT and mentioned another colleague Mary Hodge, who studies along with her master's student John Smith radioisotopes produced by cyclotron.
###output:
["J. R. Smith", "person", "has title", "Professor of Physics", "title"]
["J. R. Smith", "person", "works for", "MIT", "organization"]
["J. R. Smith", "person", "talked about", "Mary Hodge", "person"] 
["Mary Hodge", "person", "works for", "MIT", "organization"]
["John Smith", "person", "student of", "Mary Hodge", "person"]
["Mary Hodge", "person", "works on", "radioisotopes", "occupation"]
["Mary Hodge", "person", "works on", "cyclotron", "occupation"]

prompt: {0}
###output:
"""


prompt_v4 = """
Given a prompt which represents diary entry of Warren Weaver, identify as many entities and relations among them as possible and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, ENTITY 2, ENTITY 2 TYPE]. 
The relations are directed, so the order matters.
Entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, interests, occupation), technology.
Top relations of interest: "works for", "works with", "student of" (i.e. link students with their teachers/advisors), "talked about" (i.e. a person talking about another person), "talked with" (i.e. a person talking with another person), "works on" (i.e. assignment of persons to their occupation, work, specialisation, research discipline, interests, technology etc.).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R." - in output relations, always state full names.
Note that organizations (universities, their departments) are often shortened, for example: "University of California" is written as "U. of Cal." or just "U. Cal.", "Department of Physics" is written as "Dept. Phys." etc. - in output relations, always state full names.

Example:
prompt: J.R.Smith, Prof. Phys., is employed by MIT and mentioned another colleague Mary Hodge. H. studies along with her master's student John Smith radioisotopes produced by cyclotron.
###output:
["J. R. Smith", "person", "has title", "Professor of Physics", "title"]
["J. R. Smith", "person", "works for", "MIT", "organization"]
["J. R. Smith", "person", "talked about", "Mary Hodge", "person"] 
["Mary Hodge", "person", "works for", "MIT", "organization"]
["John Smith", "person", "student of", "Mary Hodge", "person"]
["Mary Hodge", "person", "works on", "radioisotopes", "occupation"]
["Mary Hodge", "person", "works on", "cyclotron", "occupation"]

prompt: {0}
###output:
"""


prompt_v5 = """
Given a prompt which represents a page from a diary of Warren Weaver (a.k.a. WW), identify as many entities and relations among them as possible and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, ENTITY 2, ENTITY 2 TYPE]. 
The relations are directed, so the order matters.
Entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, technology, interests etc.).
Top relations of interest: "works for", "works with", "student of" (i.e. link students with their teachers/advisors), "talked about" (i.e. a person talking about another person), "talked with" (i.e. a person talking with another person), "works on" (i.e. assignment of persons to their occupation), "wrote on" (i.e. link the author to the date of the diary entry).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R.".
Note that organizations (universities, their departments) are often shortened, for example: "University of California" is written as "U. of Cal." or just "U. Cal.", "Department of Physics" is written as "Dept. Phys." etc.

Always output only full entity names, and not all the shortened (abbreviated) versions of the same entity.

Example:
prompt: Friday, Feb 19, 2023
WW visits Dept. of Phys., U. of PA, with Jose Jewell.
Peter Stafford (Prof.Phys.) shows his research on magnets.
WW has lunch with Dr. William Meade (Prof.Org.Chem.) at Johns Hopkins. William discusses with him the proposed study of organic reactions by calorimeter. He and his former student, Andrews, work on it. 
During the latter part of the lunch, J.W. Allen comes in. A. works with radioisotopes produced by cyclotron.
###output:
["Warren Weaver", "person",  "wrote on", "Friday, February 19, 2023", "date"]
["Warren Weaver", "person", "visits", "Department of Physics, University of Pennsylvania", "organization"]
["Warren Weaver", "person", "talked with", "Jose Jewell", "person"]
["Jose Jewell", "person", "works for", "Department of Physics, University of Pennsylvania", "organization"]
["Warren Weaver", "person", "talked with", "Peter Stafford", "person"]
["Jose Jewell", "person", "talked with", "Peter Stafford", "person"]
["Peter Stafford", "person", "works for", "Department of Physics, University of Pennsylvania", "occupation"]
["Peter Stafford", "person", "has title", "Professor of Physics", "title"]
["Peter Stafford", "person", "works on", "magnets", "occupation"]
["Warren Weaver", "person", "talked with", "William Meade", "person"]
["William Meade", "person", "has title", "Professor of Organic Chemistry", "title"]
["William Meade", "person", "works for", "Johns Hopkins University", "organization"]
["William Meade", "person", "works on", "organic reactions", "occupation"]
["William Meade", "person", "works on", "calorimeter", "occupation"]
["William Meade", "person", "talked about", "Andrews", "person"]
["Andrews", "person", "student of", "William Meade", "person"]
["Andrews", "person", "works on", "organic reactions", "occupation"]
["Andrews", "person", "works on", "calorimeter", "occupation"]
["William Meade", "person", "works with", "Andrews", "person"]
["Andrews", "person", "works for", "Johns Hopkins University", "organization"]
["Warren Weaver", "person", "talked with", "J. W. Allen", "person"]
["William Meade", "person", "talked with", "J. W. Allen", "person"]
["J. W. Allen", "person", "works for", "Johns Hopkins University", "organization"]
["J. W. Allen", "person", "works on", "radioisotopes", "occupation"]
["J. W. Allen", "person", "works on", "cyclotron", "occupation"]

prompt: {0}
###output:
"""


prompt_v6 = """Given a prompt which represents a page from a diary of Warren Weaver (a.k.a. WW), identify all named entities and relations among them and output them in the JSON format, where each entity has unique integer ID, property `name` and possibly additional relevant properties. Relations refer to the entities using their IDs and can also have properties. The relations are directed.
Top entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, technology, interests etc.).
Top relations of interest: "works for", "works with", "student of", "talked about", "talked with", "works on" (i.e. assignment of persons to their occupations).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R.".
Note that organizations (universities, their departments) are often shortened, for example: "University of California" becomes "U. Cal.".
Always output only entities with complete/full names.

Example:
prompt: FBH
Friday, Feb 19, 2023
WW visits Dept. of Phys. at U. of PA, with Dean Jose Jewell, PhD.
Dr. Peter Stafford (Prof.Phys.) shows his research on magnets and speaks of a conference on July 5, 2023.
WW has lunch with Dr. William Meade (Johns Hopkins). William discusses with him the proposed study of organic reactions measured by calorimeter. He and his former student, Andrews, work on it since January. 
During the latter part of the lunch, physicist J.W. Allen comes in. A. works with radioisotopes produced by cyclotron.
(Copy EB)
###output:
{"entities": [{"id":0,"name":"Friday, February 19, 2023","label":"diary entry date"},{"id":1,"name":"Warren Weaver","label":"person"},{"id":2,"name":"Department of Physics, University of Pennsylvania","label":"organization"},{"id":3,"name":"Jose Jewell","label":"person","titles":["Dean","PhD."]},{"id":4,"name":"Peter Stafford","label":"person","titles":["Dr.","Professor of Physics"]},{"id":5,"name":"magnets","label":"occupation","type":"technology"},{"id":6,"name":"July 5, 2023","label":"date"},{"id":7,"name":"William Meade","label":"person","title":"Dr."},{"id":8,"name":"Johns Hopkins University","label":"organization"},{"id":9,"name":"organic reactions","label":"occupation","type":"chemistry discipline"},{"id":10,"name":"calorimeter","label":"occupation","type":"technology"},{"id":12,"name":"Andrews","label":"person"},{"id":13,"name":"J. W. Allen","label":"person","titles":["physicist"]},{"id":14,"name":"radioisotopes","label":"occupation","type":"physics discipline"},{"id":15,"name":"cyclotron","label":"occupation","type":"technology"}],
"relations": [{"source":1,"target":2,"relation":"visits"},{"source":1,"target":3,"relation":"talked with"},{"source":3,"target":2,"relation":"works for"},{"source":1,"target":4,"relation":"talked with"},{"source":3,"target":4,"relation":"talked with"},{"source":4,"target":2,"relation":"works for"},{"source":4,"target":5,"relation":"works on"},{"source":4,"target":5,"relation":"talked about"},{"source":1,"target":7,"relation":"talked with","type":"lunch"},{"source":7,"target":8,"relation":"works for"},{"source":7,"target":9,"relation":"works on","since":"January 2023"},{"source":7,"target":10,"relation":"works on","since":"January 2023"},{"source":7,"target":12,"relation":"talked about"},{"source":12,"target":7,"relation":"student of"},{"source":12,"target":9,"relation":"works on","since":"January 2023"},{"source":12,"target":10,"relation":"works on","since":"January 2023"},{"source":7,"target":12,"relation":"works with"},{"source":12,"target":8,"relation":"works for"},{"source":1,"target":13,"relation":"talked with","type":"lunch"},{"source":7,"target":13,"relation":"talked with","type":"lunch"},{"source":13,"target":8,"relation":"works for"},{"source":13,"target":14,"relation":"works on"},{"source":13,"target":15,"relation":"works on"}]}
"""


prompt_v7 = """Given a prompt which represents a page from a diary of Warren Weaver (a.k.a. WW), identify all named entities and relations among them and output them in the JSON format, where each entity has unique integer ID, property `name` and possibly additional relevant properties. Relations refer to the entities using their IDs and can also have properties. The relations are directed.
Top entities of interest: person, location, organization, date, occupation (a.k.a. person's work, specialization, research discipline, technology, interests etc.).
Top relations of interest: "works for", "works with", "student of", "talked about", "talked with", "works on" (i.e. assignment of persons to their occupations).
For "talked about" relations, classify sentiment (positive, neutral or negative).

Note that persons are often first referenced by their full name, and then mentioned only by their surname or initials, for example: "A. N. Richards" becomes "Richards", "ANR", or just "R.".
Note that organizations (universities, their departments) are often shortened, for example: "University of California" becomes "U. Cal.".
Always output only entities with complete/full names.

Example:
###prompt: FBH
Friday, Feb 19, 2023
WW visits Dept. of Phys. at U. of PA, with Dean Jose Jewell, PhD.
Dr. Peter Stafford (Prof.Phys.) shows his research on magnets he's conducting since August last year.
WW has lunch with Prof. William Meade (Johns Hopkins). William discusses with him the proposed study of organic and anorganic reactions measured by calorimeter. He works on it with his former student, Dr. Andrews. M. described Andrews as a very capable man, but he's not very impressed wih PS.
During the latter part of the lunch, Professor J.W. Allen, lead nuclear physicist, comes in. A. works with radioisotopes produced by a high energy accelerator and mentions also PS and his research.
(Copy EB)
###output:
{"entities":{"diary entry date":[{"id":0,"name":"Friday, February 19, 2023"}],
"person":[{"id":1,"name":"WW","titles":[]},{"id":2,"name":"Jose Jewell","titles":["Dean", "PhD."]},{"id":3,"name":"Peter Stafford","titles":["Dr.","Professor of Physics"]},{"id":4,"name":"William Meade","titles":["Professor"]},{"id":5,"name":"Andrews","titles":["Doctor"]},{"id":6,"name":"J. W. Allen","titles":["Professor","lead nuclear physicist"]}],
"organization":[{"id":7,"name":"Department of Physics, University of Pennsylvania"},{"id":8,"name":"Johns Hopkins University"}],
"date":[{"id":9,"name":"August 2022"}],
"occupation":[{"id":10,"name":"magnets","label":"occupation","type":"technology"},{"id":11,"name":"organic and anorganic reactions","label":"occupation","type":"chemistry discipline"},{"id":12,"name":"calorimeter","label":"occupation","type":"technology"},{"id":13,"name":"radioisotopes","type":"physics discipline"},{"id":14,"name":"high energy accelerator","type":"technology"}]},
"relations":{"visits": [{"source":1,"target":7}],
"talked with":[{"source":1,"target":2},{"source":1,"target":3},{"source":2,"target":3},{"source":1,"target":4,"type":"lunch"},{"source":1,"target":6,"type":"lunch"},{"source":4,"target":6,"type":"lunch"}],
"works for":[{"source":2,"target":7},{"source":3,"target":7},{"source":4,"target":8},{"source":5,"target":8},{"source":6,"target":8}],
"works on":[{"source":3,"target":10,"since":"August 2022"},{"source":4,"target":11},{"source":4,"target":12},{"source":5,"target":11},{"source":5,"target":12},{"source":6,"target":13},{"source":6,"target":14}],
"talked about":[{"source":4,"target":5,"sentiment":"positive"},{"source":4,"target":3,"sentiment":"negative"},{"source":6,"target":3,"sentiment":"neutral"}],
"student of":[{"source":5,"target":4}],
"works with":[{"source":4,"target":5}]}}
"""

prompt_le = """Given a prompt from law enforcement domain, identify all entities and relations among them and output a list of relations in the format [ENTITY 1, ENTITY 1 TYPE, RELATION, ENTITY 2, ENTITY 2 TYPE].

Example:
prompt: Hello, this is Jane, I just saw my neighbour John Smith attacking some person with a knife! Please help!
###output:
["Jane", "person", "reported", "knife attack", "crime"]
["John Smith", "person", "committed", "knife attack", "crime"]

prompt: {0}
###output:
"""


def parse_json_output(output: str):
    d = json.loads(output)
    entities = {e['id']: e for e in d['entities']}
    for r in d['relations']:
        print(f" {entities[r['source']]['name']} -- {r['relation'].upper()} --> {entities[r['target']]['name']}")


def parse_json_output_v2(output: str):
    d = json.loads(output)
    entities = {e['id']: e for label, arr in d['entities'].items() for e in arr}
    for rel_type, arr in d['relations'].items():
        for r in arr:
            print(f" {entities[r['source']]['name']} -- {rel_type.upper()} --> {entities[r['target']]['name']}")


def openai_query(model, query):
    t_start = time.time()
    response = openai.Completion.create(engine=model, prompt=query, temperature=0.3, max_tokens=1000, top_p=1.0,
                                        frequency_penalty=0.0, presence_penalty=0.0 #, best_of=3
                                        )
    print(response['choices'][0]['text'])
    print(f"\nTime: {round(time.time() - t_start, 1)} sec")


def openai_query_azure(model, query, temperature=0.3):
    print(f"Temperature {temperature}")
    t_start = time.time()
    response = openai.Completion.create(deployment_id=model, prompt=query, temperature=temperature, max_tokens=2000)#, top_p=1.0,
                                        #frequency_penalty=0.0, presence_penalty=0.0 #, best_of=3
                                        #)
    print(response['choices'][0]['text'])
    print(f"\nTime: {round(time.time() - t_start, 1)} sec\n")

    parse_json_output_v2(response['choices'][0]['text'])


if __name__ == "__main__":

    text = """
    JOHNS HOPKINS UNIVERSITY Chemistry Department:
    Wednesday, November 9, 1932
    WW visits the Dept. with Dr. Frazer (Baker Prof. Chem.). There are 239 undergraduate and 116 graduate students of chemistry, the latter group in- cluding holders of the special State fellowships in chemistry under the New
    Plan. D.H. Andrews (Prof.Chem.) is a physical chemist specializing in thermodynamics. He is not present at the time of WW's call, but one of his assistants explains his work. He is measuring specific heats of organic compounds by a straight calorimetric method. This work is in its early stages. He is also interested in making mechanical models of various atoms from which can
    be demonstrated the theory of the Raman spectra. J.B.Mayer (Assoc. in Chem.) is a former student of G. N. Lewis and works with Max Born at Gottingen summers. He specializes in the energetics of crystal lattices. His wife, last summer, prepared the new edition of Born's treatise on this subject. In Mayer's laboratory Mrs. Wintner, wife of the mathematician, is working on an experimental problem. Andrews says that Mayer is young and impresses one as an enthusiastic and able man.
    """

    text2 = """Wednesday, November 30,1932
J.R.Schramm (U. of Penn.) by telephone
WW informs S. that the action of the Board of Trustees in April
authorized a smaller group, the Executive Committee, to make appropriations.
WW therefore prefers not to submit a request for support for 1933 to the
Board of Trustees, particularly since such action might, at this time, precipitate discussion of general policies. WW asks if it would seriously
embarrass the officers of Biological Abstracts if decision concerning support for 1933 were not made until the January meeting of the Executive Committee.
S. states that they are used to running on faith, and that they
are quite prepared to do so for a short period more.
PH
(Copy EB)"""

    text3 = """Friday, January 13, 1939. General discussion of Cornell biology situation. The results of this conversation are reflected in ww's letter of January 16th to EED. Monday, January 16, 1939. Dr. H. S. Gasser (Telephone). The Rhoads situation has not yet been decided definitely, but it is clear that G. really expects R. to remain at the R.I. G. is anxious not to cause us difficulty, and asks the latest date at which information could be given us. WW says that we could withdraw the item at the meeting if necessary; and that in fact it would not be too serious if the grant were voted and then cancelled, since the cancellation would surely occur within the same year. EB Tuesday, January 17, 1939. Dr. Vincent du Vigneaud, Cornell University Medical College, (Telephone). du V. inquires whether he is free to divide up the sum allocated to salaries in the way which will most effectively serve his purposes. There are a few hundred dollars left unallocated in this sum, which he would like to use for part-time services of a synthetic organic chemist whom he can borrow from Columbia. WW assures him he is at liberty to divide this sum as he pleases. Should he wish to make changes in the amounts allocated for salaries, for materials and supplies, etc., that could also probably be arranged, but we should be consulted. GJB EB Professor L. A. Maynard, Cornell University, and FBH (Luncheon). See FBH's diary."""

    #openai.Model.list()
    model = "text-davinci-003"
    query = prompt_v5.format(text)
    query = prompt_v7 + "\n\n###prompt: {0}\n###output:\n".format(text3)
    #query = prompt_le.format("Vlasta is the most corrupt criminal who was just seen shooting a person on a street!")
    #openai_query(model, query)
    openai_query_azure(model, query, 0.)
    #openai_query_azure(model, query, 0.1)