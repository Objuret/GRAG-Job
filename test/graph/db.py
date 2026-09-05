from __future__ import annotations

import os

import numpy as np

from harness import nim

DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")

DATASET_ID = os.environ.get("HERB_DATASET_ID", "Salesforce__HERB")

RUN_ID = os.environ.get("HERB_TAG_RUN_ID", "pilot_full_herb")

ALL_FACETS = ("topic", "entities", "activity", "temporal", "evidence")

EXCLUDED_SECTIONS = ("answerable_questions", "unanswerable_questions", "product_profile")

def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)

def _unit(a: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(a, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return a / norms

def _driver():
    from neo4j import GraphDatabase
    nim._load_dotenv()
    pw = os.environ.get("NEO4J_PASSWORD")
    if not pw:
        raise RuntimeError("NEO4J_PASSWORD is not set — add it to .env at the repo root (like NVIDIA_API_KEY).")
    uri = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, pw),
                                notifications_min_severity="OFF")

def _readable(name: str) -> str:
    return name.replace("_", " ").strip()
