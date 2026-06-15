# pilot_full_herb — Methodology and Results

**Run date:** 2026-05-14
**Dataset:** Salesforce__HERB (1 of 4 thesis datasets)
**Database:** `herb`
**Model:** `claude-haiku-4-5` (Anthropic Messages API, forced tool_use)
**Current artefact:** [`backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip`](../../backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip)

## Goal

End-to-end semantic tagging of the full HERB corpus into Neo4j, producing
graph-native tag edges with continuous, differentiable weights suitable for
retrieval ranking.

## Method

The design — and the reasoning behind each decision — is in
[`herb_tagging_schema.md`](herb_tagging_schema.md). The short version:

1. **`select`** picks the chunks to tag. For this run, every chunk in the
   dataset (selection mode `all`).
2. **`extract` (two-pass)** runs per chunk:
   - Pass 1: model emits a flat tag list + a 1–3 sentence chunk description.
     No facets, no weights. Just retrieval handles.
   - Pass 2: model scores each pass-1 tag against each of 5 facets (`topic`,
     `entities`, `activity`, `temporal`, `evidence`). The model does NOT emit
     `w_chunk` — that is computed in code from the 5-element facet vector.
3. **`describe`** runs per file: model writes a 2–3 sentence file summary
   based on its chunks' descriptions.
4. **`score`** runs per file (batched): all chunks of the file are scored in
   one call so the model differentiates representativeness comparatively, not
   in isolation.
5. **`analyze`** reads everything back from Neo4j and writes `analysis.md`.

### Why the model does not emit `w_chunk`

Across smoke pilots, model-verbalised float weights anchored hard on round
values (0.7, 0.8, 0.9 …). The two-pass design pulls `w_chunk` out of the
model's emit surface entirely and derives it from the facet vector:

```text
w_chunk = strength × coverage_bonus

strength       = sqrt(sum(f²) / N)
coverage_bonus = ((sum(f))² / (N × sum(f²))) ^ α      with N = 5, α = 0.25
```

A tag with `1.00` in two facets scores higher than a tag with `1.00` in one,
by design. This single change produced the granularity jump shown below.

### Multi-facet emission

For each tag, a `HAS_TAG` edge is written for the primary facet
(`argmax(facets)`) plus one edge per facet scoring ≥ 0.50. Same tag, different
facets → multiple edges, each with the facet's own `w_facet`. Same `w_chunk`
across those edges (it's a per-tag property).

## Results

### Coverage

| Metric | Value |
|---|---:|
| Chunks selected | 5843 |
| Chunks with description | 5843 (100%) |
| Chunks with `relevance_to_file` | 5843 (100%) |
| Files described | 33 / 33 |
| `:HAS_TAG` edges written | 255,288 |
| Unique tag names | 25,896 |
| Multi-facet tags | 22,083 (85% of unique names) |
| Evidence kinds tagged | 14 / 14 |

### Weight distributions

| Axis | n | distinct @ 2dp | range | mean | stdev |
|---|---:|---:|---|---:|---:|
| `w_chunk` (derived) | 255,288 | **76** | 0.03–0.91 | 0.56 | 0.11 |
| `w_facet` (model) | 255,288 | 21 | 0.10–1.00 | 0.81 | 0.16 |
| `w_chunk_file` (model, batched) | 5,843 | **86** | 0.05–1.00 | 0.78 | 0.13 |

76 distinct `w_chunk` values across a quarter-million edges, 86 distinct
`w_chunk_file` values across 5843 chunks — both genuinely continuous rather
than collapsed to a handful of round numbers.

### Anchoring rate (`w_chunk` only multiple of 0.1 within 0.025)

- pilot_001 single-pass: **85%** on round anchors
- pilot_format_smoke single-pass: 85%
- pilot_format_smoke two-pass, model-emitted w_chunk: 47%
- **pilot_full_herb two-pass, derived w_chunk: 12.3%**

Reducing anchoring from 85% to 12% was the load-bearing goal of the design
work; this is the evidence it succeeded.

### Failure handling

Initial run had 33 errors:
- 26 chunks failed extract with `RateLimitError 429` (transient).
- 7 files failed score with `max_tokens=4096` truncation on files with > 210
  chunks — the JSON output exceeded the cap and came back malformed.

Both were recovered by [`recovery.py`](../../backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z/recovery.py)
in the snapshot directory:
- `max_tokens` raised to 8192 in `pipeline.py`.
- The 26 chunks re-extracted (two-pass) and written to Neo4j.
- The 7 file batches re-scored with the new cap.
- 17 chunks that the model dropped from large batched score responses were
  filled with single-chunk score calls.

Final state: 5843 / 5843 chunks complete. Recovery cost: ~$0.67.

### Cost and timing

| | Value |
|---|---:|
| Wall time (main run) | ~3.5 hours |
| Concurrency | 4 |
| Total API calls (main + recovery) | 11,785 |
| Total input tokens | 22.96M |
| Total output tokens | 10.07M |
| **Total cost** | **~$73.40** |

### Per-stage cost averages

| Stage | Calls | Avg in | Avg out | $/call |
|---|---:|---:|---:|---:|
| extract (pass 1) | 5843 | 1,687 | 315 | $0.0033 |
| score_tags (pass 2) | 5817 | 2,044 | 1,381 | $0.0089 |
| describe | 33 | 14,924 | 189 | $0.0159 |
| score (batched per file) | 33 | 15,156 | 3,482 | $0.0326 |

## Artefacts

The committed, portable artefact for the completed HERB run is:

```
backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z.zip
```

Expand it locally when you need the full run directory. Its expected expanded
layout is:

```
backend/data/tagging_runs/pilot_full_herb_snapshot_20260514T052226Z/
├── run.json                        # selected 5843 chunk IDs + pilot metadata
├── extract.log
├── describe.log
├── score.log
├── analyze.log
├── io.jsonl                        # every API call's full I/O (70 MB)
├── errors.jsonl                    # the 33 failures (rate limit + truncation)
├── analysis.md                     # analysis written immediately post-run (had gaps)
├── analysis_final.md               # analysis regenerated after recovery (complete)
├── neo4j_chunks.jsonl              # initial chunk export
├── neo4j_files.jsonl               # file descriptions export
├── neo4j_edges.jsonl               # initial edges export (254,082)
├── recovery.py                     # the gap-filling script
├── recovery_io.jsonl               # recovery API calls
├── recovery_errors.jsonl           # empty
├── neo4j_chunks_post_recovery.jsonl
├── neo4j_edges_post_recovery.jsonl # 255,288 edges
└── neo4j_chunks_final.jsonl        # 100%-coverage final chunk export
```

The loose expanded directory, `pilot_full_herb/`, and earlier smoke-run
folders are build/history working material unless explicitly re-materialized
from the zip for inspection. The zip is the thing to push, move, and treat as
the current HERB snapshot.

The Neo4j `herb` database remains live with this run's outputs written under
`run_id = "pilot_full_herb"`. The snapshot lets the run be reconstructed even
if Neo4j is wiped.

## Notes for the next iteration

- **Telegram mode is severe.** Median tags-per-chunk is 42, max 164. The
  multi-facet expansion contributes. Tuning `MULTI_FACET_THRESHOLD` upward
  from 0.50 (current) would cut edge count significantly.
- **`unanswerable_question_batch` is degenerate.** All weights came back at
  the top of the range for this kind — the model treats all unanswered
  questions as equally important. Consider a kind-specific prompt or skip
  weights for this kind.
- **w_facet still anchors more than w_chunk.** Only 21 distinct values vs 76
  for derived w_chunk. The derivation indirectly stretches the distribution
  by combining 5 anchored inputs; the raw facet score itself is still 0.05-
  step. If higher facet resolution becomes important, that's the next lever.
- **`temporal` is sparsely used.** Most evidence kinds rarely include verbatim
  date expressions; this is expected.
