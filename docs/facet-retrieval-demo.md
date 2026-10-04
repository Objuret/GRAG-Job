# Recompute a frozen prepared question

This CLI runs the actual experimental `retrieve_prepared_query` pipeline against
the existing safe Volmax snapshot and seven captured questions. It computes new
route scores, nomination and recovered contexts; it does not display saved ranks.
No model, DB, network, raw product file or benchmark is read.

From the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe -X utf8 tools/facet_retrieval_demo.py --list

.venv\Scripts\python.exe -X utf8 tools/facet_retrieval_demo.py `
  --question-id sentiment_intended_use --reading-index 0 `
  --coefficients 1 .25 .25 .25 .25 --source-character-budget 72000 `
  --output output/research/2026-09-22-joint-streams/independent_sources/demo_run/my-run

# Optional: reuse the saved, verified structural area for this captured reading.
.venv\Scripts\python.exe -X utf8 tools/facet_retrieval_demo.py `
  --question-id independent_durable_messages_current_models --reading-index 0 `
  --coefficients 1 .25 .25 .25 .25 --source-character-budget 72000 `
  --verified-area `
  --output output/research/2026-09-22-joint-streams/independent_sources/demo_run/my-area-run
```

Choose a **new** output directory for each run. Coefficients and budget are
required; coefficient order is topic, temporal, why, activity, concreteness.
Topic must be positive; auxiliaries and budget nonnegative. Reading indices
identify the separate saved SCORE observations, not newly generated readings.

Outputs:

- `retrieval.json`: complete selected source text, all query tags/readings,
  full ranking witnesses, original versus recovered depths and trigger IDs,
  complete frontiers, policy and input hashes.
- `ranking_arrays.npz`: all scores, ranks, per-facet profiles and direct/graph
  route tensors; arrays align to its `chunk_ids`.
- `REPORT.md`: concise configuration, selection counts and context index.

The pipeline retains each chunk's own facet evidence. A recovered sibling does
not inherit the trigger's score or facet support. The CLI validates frozen input
hashes and alignment before retrieval and refuses to overwrite existing outputs.

This is prepared-query integration, **not a raw-query application**. Captured
interpretation defects remain visible, including the sensor-pivot merger reading.
The five coefficients are an explicit provisional policy, not learned utilities.
The demo uses global nomination, original shared Product+Channel groups, locator
adjacency and exact-record recovery. By default it does not use area recruitment.
`--verified-area` explicitly reuses the selected reading's archived membership
and provenance from `scope_recruitment/run`, verifying manifest/archive hashes.
It calls the existing `recruit_with_verified_area` on freshly computed scores:
global access remains available, and an unresolved saved area falls back to the
global list. It introduces no new name resolution, aliases, gates or score boosts.
Both sentiment questions remain unresolved under this particular saved policy.
It does not reproduce the later Product-only propagation intervention or the
separate Tag-path area resolution experiment.

Opt-in output includes the archived area/provenance and stream IDs in JSON, and
`recruitment_stream_scores` in the numeric archive. Contexts retain their own
unchanged facet witnesses alongside updated recovery triggers. Earlier demo
artifacts remain immutable; their input code hashes describe the historical
version, preserved under `demo_run/source_versions/`, not the current CLI.

The budget counts saved source characters, including overlap, and admits a prefix
of complete frontiers. It is not a production token or serialized-context budget.
No retrieval-quality or semantic-calibration claim follows from a successful run.

## A separately captured query bundle

Pass `--query-bundle PATH` to read `PATH/query_capture/query_captures.json` and
`PATH/query_snapshot/{manifest.json,queries.json,arrays.npz}`. The original graph
snapshot remains fixed. All capture hashes and query/graph alignment checks still
apply. `--list --query-bundle PATH` lists that bundle without recomputing retrieval.
The default bundle remains the original seven-question archive.

With `--verified-area`, a new capture may reuse an archived structural area only
when its question ID, exact raw question and reading ID match that saved record.
New descriptions, tags and facet readings are computed normally from the selected
bundle; no saved relevance scores or rankings are replayed. This is not a scope
resolver for arbitrary new questions.

`tools/facet_fresh_smoke.py --stage prepare` freezes orchestration under
`independent_sources/fresh_smoke` after its `PROTOCOL.md` exists. It makes no model
calls. Subsequent stages are explicit and separate:

```powershell
.venv\Scripts\python.exe -X utf8 tools/facet_fresh_smoke.py --stage capture
.venv\Scripts\python.exe -X utf8 tools/facet_fresh_smoke.py --stage embed
.venv\Scripts\python.exe -X utf8 tools/facet_fresh_smoke.py --stage retrieve
```

Capture invokes the unchanged existing tool with a maximum of seven GENERATE and
fourteen SCORE attempts. Embedding invokes the existing pinned local snapshot
tool. Retrieval runs all fourteen saved readings through this demo, with explicit
`1 .25 .25 .25 .25`, 72,000 characters and the archived verified-area option.
No stage retries uncertain calls. All seven generations and fourteen SCORE
readings must succeed before downstream stages; failures remain recorded and
block the first smoke rather than silently filtering or replacing inputs.
Already completed direct capture/embedding outputs can be verified and adopted
without calls; incomplete started work is refused. Stage completion is execution
evidence, not a generated retrieval-quality metric.
