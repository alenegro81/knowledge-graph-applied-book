PIP=../../venv/bin/pip
ENV=../../venv/bin/activate
PYTHON=python

download:
	mkdir -p ../../dataset/ontology/snomed/
	# curl "https://uts-ws.nlm.nih.gov/download?url=https://download.nlm.nih.gov/mlb/utsauth/USExt/SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z.zip&apiKey=PUT_YOUR_API_KEY_HERE" -o ../../dataset/ontology/snomed/SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z.zip
	unzip ../../dataset/ontology/snomed/SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z.zip -d ../../dataset/ontology/snomed/
	mv ../../dataset/ontology/snomed/SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z/Full/Terminology/sct2_Relationship_Full_US1000124_20220901.txt ../../dataset/ontology/snomed/sct2_Relationship_Full_US1000124_20220901.txt 
init:
	$(PIP) install -r requirements.lock

import:
	source $(ENV)
	PYTHONPATH=../../ python importer/import_snomed_rels.py
