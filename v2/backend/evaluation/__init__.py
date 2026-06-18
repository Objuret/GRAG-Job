"""v2 evaluation middle layer.

Shared, arm-agnostic plumbing that every eval pipeline (sql_agent, and the
graph/lucene/vector arms as they come online) drives to produce one common
output shape. An arm's job ends at handing this layer its per-question result;
this layer owns the run frame, the per-question row shape, the cohort manifest,
and the gold-set loader — so a downstream scorer reads the same `ragas-export`
JSONL regardless of which arm produced it.

This is v2-native and INDEPENDENT of v1 (no port, no shared import).
"""
