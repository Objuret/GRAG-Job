"""RAGAS evaluation for the HERB browser pipeline.

Consumer half of the producer/consumer split. The producer is the headless
harness `frontend/scripts/ragas-export.ts`, which runs the REAL browser
pipeline (interpret -> retrieve -> answer) against the live `herb` graph and
writes one JSONL row per question. This package only reads that JSONL — it has
no Neo4j, no LLM pipeline, no dependency on the legacy clustering layer.
"""
