# HERB Tagging Pilot — `pilot_001`

- Generated: 2026-05-13T09:50:46.896373+00:00
- Model: `claude-haiku-4-5`
- Database: `herb`
- Provider: `anthropic` (structured output via forced tool_use)
- Sample: 10 chunks across 3 files

## Caveat
This pilot sampled 10 chunks across some subset of the 33 files.
File descriptions were generated only from the sampled chunks of each file,
not from every chunk in the file. The w_chunk_file scores are therefore relative
to a partial picture of each file. Comparable cross-file scoring requires a full run.

## Per-chunk dump

### `0c37d412cb740af55a668dee`  (ordinal 2)
- file: `Salesforce__HERB/products/CollaborateForce.json`
- w_chunk_file: `0.95`
- content (first 400 chars): `{   "slack": [     {       "Channel": {         "name": "planning-CollaborateForce",         "channelID": "ch-abaix-c92927"       },       "Message": {         "User": {           "userId": "slack_admin_bot",           "timestamp": "2026-05-23T00:00:00",           "text": "@eid_94fb5d84 created this channel on 2026-05-23 00:00:00. This is the very beginning of the planning-abAIX channel.",        `
- description: A Slack conversation in the planning-CollaborateForce channel where team members collaborate on refining a Market Research Report for abAIX, an AI-powered collaboration tool. The team provides feedback on various sections including Executive Summary, Market Overview, Product Features, Target Audience, and Challenges & Risks, with the project lead (Charlie) accepting suggestions for improvements.
- tags:
    - **topic**: `market_research_report` (w_c=0.9, w_f=1.0), `abaix_product` (w_c=0.85, w_f=1.0), `ai_collaboration_tools` (w_c=0.7, w_f=1.0), `product_positioning` (w_c=0.6, w_f=0.9)
    - **entities**: `abaix` (w_c=0.9, w_f=1.0), `planning_collaborateforce` (w_c=0.8, w_f=1.0), `charlie_eid_94fb5d84` (w_c=0.8, w_f=1.0), `alice_eid_782010a4` (w_c=0.5, w_f=1.0), `bob_eid_272ed674` (w_c=0.5, w_f=1.0)
    - **activity**: `collaborative_feedback_and_discussion` (w_c=0.9, w_f=1.0), `report_refinement` (w_c=0.85, w_f=1.0), `sharing_market_research_report` (w_c=0.8, w_f=1.0), `team_members_joining` (w_c=0.4, w_f=1.0), `channel_creation` (w_c=0.3, w_f=1.0)
    - **temporal**: `2026_05_25` (w_c=0.7, w_f=1.0), `09_28_00_to_09_48_00` (w_c=0.6, w_f=1.0), `2026_05_23` (w_c=0.3, w_f=1.0)
    - **evidence**: `suggestion_add_industry_success_examples` (w_c=0.7, w_f=0.9), `suggestion_elaborate_on_real_time_collaboration_with_examples` (w_c=0.7, w_f=0.9), `suggestion_add_user_feedback_and_case_studies` (w_c=0.7, w_f=0.9), `suggestion_include_ai_growth_statistics` (w_c=0.6, w_f=0.9), `suggestion_address_regulatory_challenges` (w_c=0.5, w_f=0.9)

### `bfed7e9e8bd26deeaf8df80c`  (ordinal 93)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_35e32fec": {     "employee_id": "eid_35e32fec",     "name": "Ian Taylor",     "role": "Engineering Lead",     "location": "Sydney",     "org": "einstein"   } }`
- description: Employee record for Ian Taylor, an Engineering Lead based in Sydney working for the Einstein organization.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `organizational_structure` (w_c=0.6, w_f=0.9)
    - **entities**: `ian_taylor` (w_c=1.0, w_f=1.0), `einstein` (w_c=0.8, w_f=1.0), `sydney` (w_c=0.7, w_f=1.0)
    - **activity**: `engineering_leadership` (w_c=0.9, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `ae6661fd144ff3d8c1ddda0b`  (ordinal 150)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_f86a00ce": {     "employee_id": "eid_f86a00ce",     "name": "Fiona Smith",     "role": "UX Researcher",     "location": "Seattle",     "org": "tableau"   } }`
- description: Employee record for Fiona Smith, a UX Researcher based in Seattle working at Tableau.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `ux_research` (w_c=0.8, w_f=0.9)
    - **entities**: `fiona_smith` (w_c=1.0, w_f=1.0), `tableau` (w_c=0.9, w_f=1.0), `seattle` (w_c=0.7, w_f=1.0)
    - **activity**: `ux_research` (w_c=0.8, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `db48edbd3d4fa726c6adfd84`  (ordinal 161)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_1faba5d2": {     "employee_id": "eid_1faba5d2",     "name": "Charlie Davis",     "role": "QA Specialist",     "location": "Berlin",     "org": "mulesoft"   } }`
- description: Employee record for Charlie Davis, a QA Specialist based in Berlin working for MuleSoft.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `quality_assurance` (w_c=0.8, w_f=0.9)
    - **entities**: `charlie_davis` (w_c=1.0, w_f=1.0), `mulesoft` (w_c=0.9, w_f=1.0), `berlin` (w_c=0.8, w_f=1.0)
    - **activity**: `qa_testing` (w_c=0.7, w_f=0.8)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `a5cfb88f340cc12659fa42e5`  (ordinal 174)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_6b76916e": {     "employee_id": "eid_6b76916e",     "name": "George Jones",     "role": "QA Specialist",     "location": "Seattle",     "org": "mulesoft"   } }`
- description: Employee record for George Jones, a QA Specialist based in Seattle working for MuleSoft.
- tags:
    - **topic**: `employee_information` (w_c=1.0, w_f=1.0), `quality_assurance` (w_c=0.8, w_f=0.9)
    - **entities**: `george_jones` (w_c=1.0, w_f=1.0), `mulesoft` (w_c=0.9, w_f=1.0), `seattle` (w_c=0.8, w_f=1.0)
    - **activity**: `qa_specialist_role` (w_c=0.9, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `d7fe4bbf728b7d6b76d5a415`  (ordinal 197)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_b7f0726e": {     "employee_id": "eid_b7f0726e",     "name": "Charlie Miller",     "role": "Software Engineer",     "location": "London",     "org": "salesforce"   } }`
- description: Employee record for Charlie Miller, a Software Engineer at Salesforce located in London.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `organizational_structure` (w_c=0.6, w_f=0.9)
    - **entities**: `charlie_miller` (w_c=1.0, w_f=1.0), `salesforce` (w_c=0.9, w_f=1.0), `london` (w_c=0.8, w_f=1.0)
    - **activity**: `software_engineering` (w_c=0.9, w_f=1.0)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `3870d2a9ad0b03eccd4ffbde`  (ordinal 207)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.85`
- content (first 400 chars): `{   "eid_b20b58ad": {     "employee_id": "eid_b20b58ad",     "name": "Julia Jones",     "role": "Software Engineer",     "location": "Sydney",     "org": "salesforce"   } }`
- description: Julia Jones is a Software Engineer at Salesforce located in Sydney.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `software_engineering` (w_c=0.8, w_f=1.0)
    - **entities**: `julia_jones` (w_c=1.0, w_f=1.0), `salesforce` (w_c=0.9, w_f=1.0), `sydney` (w_c=0.7, w_f=1.0)
    - **activity**: `software_engineering` (w_c=0.8, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `c5c0ec5ce3e3fb775fdc814f`  (ordinal 216)
- file: `Salesforce__HERB/metadata/employee.json`
- w_chunk_file: `0.75`
- content (first 400 chars): `{   "eid_9a9cf08a": {     "employee_id": "eid_9a9cf08a",     "name": "Emma Davis",     "role": "Marketing Research Analyst",     "location": "London",     "org": "salesforce"   } }`
- description: Emma Davis is a Marketing Research Analyst based in London working for Salesforce.
- tags:
    - **topic**: `employee_profile` (w_c=1.0, w_f=1.0), `marketing_research` (w_c=0.8, w_f=0.9)
    - **entities**: `emma_davis` (w_c=1.0, w_f=1.0), `salesforce` (w_c=0.9, w_f=1.0), `london` (w_c=0.7, w_f=1.0)
    - **activity**: `marketing_research_analysis` (w_c=0.8, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `4552dddeaae01ef9721c9c57`  (ordinal 58)
- file: `Salesforce__HERB/metadata/customers_data.json`
- w_chunk_file: `0.95`
- content (first 400 chars): `{   "name": "Bob Davis",   "role": "AI Engineer",   "company": "DataSolutions",   "id": "CUST-0059" }`
- description: A customer profile for Bob Davis, an AI Engineer at DataSolutions, identified by customer ID CUST-0059.
- tags:
    - **topic**: `customer_profile` (w_c=1.0, w_f=1.0), `professional_identity` (w_c=0.9, w_f=0.9)
    - **entities**: `bob_davis` (w_c=1.0, w_f=1.0), `datasolutions` (w_c=0.9, w_f=1.0), `cust_0059` (w_c=0.8, w_f=1.0)
    - **activity**: `works_as_ai_engineer` (w_c=0.9, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

### `88c460e71accfbd1b112e83f`  (ordinal 60)
- file: `Salesforce__HERB/metadata/customers_data.json`
- w_chunk_file: `0.95`
- content (first 400 chars): `{   "name": "Helen Davis",   "role": "Software Engineer",   "company": "TechCorp",   "id": "CUST-0061" }`
- description: Customer profile for Helen Davis, a Software Engineer at TechCorp, identified by customer ID CUST-0061.
- tags:
    - **topic**: `customer_profile` (w_c=1.0, w_f=1.0), `employment` (w_c=0.8, w_f=0.9)
    - **entities**: `helen_davis` (w_c=1.0, w_f=1.0), `techcorp` (w_c=0.9, w_f=1.0)
    - **activity**: `software_engineering` (w_c=0.8, w_f=0.9)
    - **temporal**: (none)
    - **evidence**: `raw_data` (w_c=1.0, w_f=1.0)

## Per-file dump

### `4b5c6a20d903a7b89a9cdf21`
- rel_path: `Salesforce__HERB/products/CollaborateForce.json`
- chunks sampled: 1
- file description: This file documents a Slack conversation from the planning-CollaborateForce channel where a team collaborates on developing a Market Research Report for abAIX, an AI-powered collaboration tool. Team members provide iterative feedback and suggestions on key report sections including the Executive Summary, Market Overview, Product Features, Target Audience, and Challenges & Risks, with the project lead Charlie incorporating these improvements into the document.

### `85c7be7ca8f554f27cd84f35`
- rel_path: `Salesforce__HERB/metadata/employee.json`
- chunks sampled: 7
- file description: This file contains employee records for seven professionals working across various Salesforce-related organizations including Salesforce, Einstein, Tableau, and MuleSoft, with roles spanning engineering, UX research, QA, and marketing. The employees are geographically distributed across major tech hubs including Sydney, Seattle, Berlin, and London. The data appears to be a structured employee directory or HR metadata file tracking personnel information across multiple organizational units.

### `d17fbfa2d9071000cfcf9a4f`
- rel_path: `Salesforce__HERB/metadata/customers_data.json`
- chunks sampled: 2
- file description: This file contains customer profile data from Salesforce, specifically storing information for individual customers including their names, job titles, employer organizations, and unique customer identifiers. The chunk descriptions indicate it includes profiles for customers such as Bob Davis (AI Engineer at DataSolutions, CUST-0059) and Helen Davis (Software Engineer at TechCorp, CUST-0061).

## Tag stats

- total tag-edges: 84
- unique tag names (across facets): 58
- edges per facet:
    - topic: 22 edges, 10/10 chunks have ≥1 tag
    - entities: 31 edges, 10/10 chunks have ≥1 tag
    - activity: 14 edges, 10/10 chunks have ≥1 tag
    - temporal: 3 edges, 1/10 chunks have ≥1 tag
    - evidence: 14 edges, 10/10 chunks have ≥1 tag

- top tag occurrences (facet/name → count):
    - evidence/`raw_data`: 9
    - topic/`employee_profile`: 6
    - entities/`salesforce`: 3
    - activity/`software_engineering`: 3
    - topic/`organizational_structure`: 2
    - entities/`sydney`: 2
    - entities/`seattle`: 2
    - topic/`quality_assurance`: 2
    - entities/`mulesoft`: 2
    - entities/`london`: 2
    - topic/`customer_profile`: 2
    - topic/`market_research_report`: 1
    - topic/`abaix_product`: 1
    - topic/`ai_collaboration_tools`: 1
    - topic/`product_positioning`: 1
    - entities/`planning_collaborateforce`: 1
    - entities/`abaix`: 1
    - entities/`charlie_eid_94fb5d84`: 1
    - entities/`alice_eid_782010a4`: 1
    - entities/`bob_eid_272ed674`: 1

## Weight distributions

### w_chunk (per-tag centrality)
- n = 84
- min/median/max = 0.30 / 0.90 / 1.00
- mean = 0.833
- stdev = 0.168
- distinct values = 9
- histogram (0.1 bins):
      [0.0, 0.1)   0
      [0.1, 0.2)   0
      [0.2, 0.3)   0
      [0.3, 0.4)   2 ##
      [0.4, 0.5)   1 #
      [0.5, 0.6)   3 ###
      [0.6, 0.7)   5 #####
      [0.7, 0.8)  10 ##########
      [0.8, 0.9)  20 ####################
      [0.9, 1.0]  43 ###########################################

### w_facet (per-tag facet-fit)
- n = 84
- min/median/max = 0.80 / 1.00 / 1.00
- mean = 0.973
- stdev = 0.047
- distinct values = 3
- histogram (0.1 bins):
      [0.0, 0.1)   0
      [0.1, 0.2)   0
      [0.2, 0.3)   0
      [0.3, 0.4)   0
      [0.4, 0.5)   0
      [0.5, 0.6)   0
      [0.6, 0.7)   0
      [0.7, 0.8)   0
      [0.8, 0.9)   1 #
      [0.9, 1.0]  83 ###################################################################################

### w_chunk_file (per-chunk file representativeness)
- n = 10
- min/median/max = 0.75 / 0.85 / 0.95
- mean = 0.870
- stdev = 0.060
- distinct values = 3
- histogram (0.1 bins):
      [0.0, 0.1)   0
      [0.1, 0.2)   0
      [0.2, 0.3)   0
      [0.3, 0.4)   0
      [0.4, 0.5)   0
      [0.5, 0.6)   0
      [0.6, 0.7)   0
      [0.7, 0.8)   1 #
      [0.8, 0.9)   6 ######
      [0.9, 1.0]   3 ###

## Round-number anchoring check

If the model anchors to round values, you'll see most mass at multiples of 0.1.

### w_chunk → nearest 0.1
- 0.3:   2  (  2.4%)  #
- 0.4:   1  (  1.2%)
- 0.5:   3  (  3.6%)  #
- 0.6:   5  (  6.0%)  ##
- 0.7:  10  ( 11.9%)  #####
- 0.8:  20  ( 23.8%)  ###########
- 0.9:  16  ( 19.0%)  #########
- 1.0:  27  ( 32.1%)  ################

### w_facet → nearest 0.1
- 0.8:   1  (  1.2%)
- 0.9:  21  ( 25.0%)  ############
- 1.0:  62  ( 73.8%)  ####################################

### w_chunk_file → nearest 0.1
- 0.8:   7  ( 70.0%)  ###################################
- 0.9:   3  ( 30.0%)  ###############

## Cost / perf

- total Groq calls (incl retries): 23
- calls per stage: {'extract': 10, 'describe': 3, 'score': 10}
- total prompt tokens: 29026
- total completion tokens: 5317
- summed duration: 45347 ms (45.3 s)
