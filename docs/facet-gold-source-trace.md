# HERB gold-source pointers through retrieval

The seven earlier “development questions” were authored from corpus passages.
They were not HERB benchmark questions, including from outside gold100. Following
the user's correction on 2026-09-22, new homemade-question work stopped before
question construction or model calls. The replacement diagnostic uses existing
HERB citation IDs as pointers, joined after retrieval.

## Run and inspect

```powershell
.venv/Scripts/python.exe -B -X utf8 tools/facet_gold_trace.py
```

Output: `output/research/2026-09-22-gold-source-trace/index.html`, a standalone
interactive report. Select a saved run and question ID, then expand a gold source
to see every mapped chunk. Each chunk shows its score rank, scope nomination,
recovered position, cumulative serialized cost, delivery status and winning facet
paths, with static tag links and structural memberships available underneath.
Source-level rank and position summaries are independent minima; the per-chunk
rows provide actual paths.

`--run PATH` can be repeated to place multiple compatible saved joint-arm runs in
the same report. It does not rerun retrieval. `--subset PATH` selects an existing
ID list; the default is the chosen `data/gold100.jsonl`. The current report traces
the completed ten-question smoke and maps the other 90 questions without claiming
they were run. It does not inspect the other benchmark question sets.

The JSON files are reusable diagnostic data:

- `gold_source_index.json`: question ID → gold artifact ID → chunk IDs → tag edges
  and graph memberships; all relationships remain many-to-many.
- `chunk_delivery_index.json`: resolver-derived artifact IDs and serialized lengths
  for the 4,808 eligible chunks.
- `run_traces.json`: saved per-source/per-chunk positions and facet routes through
  the real ranking, scope, recovery and delivery stages.
- `verification.json`: counts, input/output hashes and delivery consistency checks.

## Initial result

All 3,501 distinct cited source IDs from gold100 map to the frozen eligible graph:
802 chunks and 9,281 semantic tag edges. This is graph membership, not 100% retrieval
or answer-evidence coverage.

The ten saved questions contain 508 question/source links: 164 are credited by the
actual delivery helper and 344 map to chunks in the recovered order outside the
72,000-character context. Ten delivery boundaries are partial; their IDs receive
no new credit. These counts are pooled links, not the average question recall.
The mean per-question ID recall reconstructed from the pointers is
0.33053887697655054, reproducing the evaluator's 0.3305388769765506 to floating-point
precision. Pooled ID recall is 164/508 = 0.3228346456692913.

Thus the observed missing citations in this smoke are present in the eligible
graph and retrieval order. That locates their loss at delivery for these rankings;
it does not show that expanding the budget is desirable or that each citation is
necessary to answer the question. Preserve misses as observations, not repair gates.

## Measurement boundary

The tool uses the actual resolver extracted from `artefact_v2.py`, verifies all 30
raw source files against graph-recorded SHA256, and checks that saved graph,
facet-array and resolver versions match. Raw documents are processed mechanically;
benchmark questions, answers, contexts and raw source text are not exported.
Gold citation IDs never enter query interpretation, scoring or nomination.

Saved delivery lengths, complete units, partial boundaries and credited IDs are
checked against the reconstructed unit metadata. A full graph unit can still
represent only a portion of a cited artifact. Source-ID credit therefore does not
prove that the particular answer-bearing passage was delivered. The report exposes
this distinction rather than silently treating artifact credit as claim coverage.

This is instrumentation for the user's original facet-weighting question, not a
new ranking policy, calibrated weighting result or gold-driven parameter sweep.
No model calls, embeddings, answer generation or retrieval reruns are needed.
