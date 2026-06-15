"""v2 eval baselines — thesis comparison arms for the v2 artefact (not v1).

| Module | Arm | Store |
|---|---|---|
| `lucene` | Lexical full-text on raw chunk body | Neo4j `chunk_content_ft` |
| `vector` | Dense kNN on chunk content embeddings | Neo4j `chunk_emb_content` |
| `sql_agent` | LLM + SQL tool over relational HERB | SQLite (raw JSON loader) |
"""

from .lucene import retrieve_baseline_content
from .vector import retrieve_baseline_vector

__all__ = ["retrieve_baseline_content", "retrieve_baseline_vector"]
