"""v2 ingestion spine — references-not-copies rebuild.

Fresh package: no imports from the v1 spine (tagging/, indexing/). Shared
infrastructure (shared.config) is allowed; v1 pipeline code is not.

Stages (design doc docs/v2_artefact_rebuild_design.md):
  scan -> probe -> reference -> structure -> chunk -> tag -> retrieve

Eval baselines (v2-only comparison arms): v2/baselines/{lucene,vector,sql_agent}.py
"""
