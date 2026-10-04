# Retrieval harness: Claude Code, Cursor, or a terminal

Open **C:\Coding\exjobbet\GRAG-Job** in the agent/editor. This is ordinary local
Python, JSON specifications and an HTTP UI; nothing depends on a Codex session.
Use this existing checkout and its `.venv`, since the frozen inputs and several
implementation files are local work. A fresh Git clone is not a complete bundle.

## Start here

Run these PowerShell commands from the repository root:

```powershell
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py status
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py serve --port 8770
```

Open `http://127.0.0.1:8770/`. If the server is already running, use that page;
there is no need to start another listener. For a separate server use another
port, such as 8771. The process runs in the foreground and stops with Ctrl+C.
Agents can use the CLI without a browser. No API key, running Neo4j instance,
embedder inference, interpreter call, answer generation or judge call is needed
for these **cached numeric replays**.

## Run and resume a new experiment

First verify the interface with the supplied small specification: two cases,
two policies and two coefficient vectors, eight retrievals in total.

```powershell
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py init --spec examples\retrieval-harness\smoke.json --run my-smoke
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py run --run my-smoke --workers 1 --max-jobs 1
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py status --run my-smoke
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py run --run my-smoke --workers 1
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py report --run my-smoke --metric recall_id
```

`init` freezes the requested cases, policies, coefficients, inputs and source
hashes into a new run. It refuses to reuse a run name. `run` skips completed,
hash-verified shards. Each shard is **one case × one policy across all specified
weights**. `--max-jobs` limits new shards in that invocation, not the experiment's
population. Omit it to finish all remaining shards. Workers may be 1–4; use one
coordinator per run. A writer lock prevents two agents writing the same run.

Results live in `output/research/retrieval-harness-runs/<name>/`. Keep the plan,
NPZ files and JSON completion markers together. Report rankings only include
settings completed on every case declared in that run; partial populations are
not silently compared. A hard process kill may leave `writer.lock`: inspect its
PID and confirm that coordinator and its children have exited before removing
that specific lock. Do not delete completed shards to force a resume.

If source or input hashes change, resumption fails. Keep the original versions
to resume, or initialize a new named experiment for changed semantics. Never
edit historical result files to make a provenance check pass.

## Continue the missing coefficient cross

This supplied specification crosses the existing **1,600 separate-facet-sum
policies with all 509 recorded coefficient vectors on all 95 saved queries**:

```powershell
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py init --spec examples\retrieval-harness\weights-cross.json --run weights-cross-v1
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py run --run weights-cross-v1 --workers 3
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness.py report --run weights-cross-v1 --metric recall_id
```

That is **77,368,000 retrievals**, not the already-completed small weight grid.
The commands above are instructions, not a record that this large run has been
launched. Use `--max-jobs 1` first to measure local speed if needed. It reruns the
three previously weighted constructions within the broader declared experiment.
This finishes that finite family; it does not exhaust new path algorithms,
alternative interpreters, new edge measurements or continuous weights.

Custom coefficients currently apply only to `separate_facet_sum`. The runner
rejects incompatible combinations instead of silently ignoring weights.

## Unattended runs: the keep-alive wrapper (2026-09-22)

`tools/retrieval_harness_keepalive.py` runs either runner as a detached child,
keeps the machine from idle-sleeping, tees the child's output to `run.log`,
writes `heartbeat.json` (shards done, rate over the last ten minutes, estimated
finish) in the run folder, relaunches the child if it exits without a final
status, stops when a relaunch completes no shard (a deterministic failure) or
the same shard fails twice, and removes a stale `writer.lock` only when it
names this host and a PID that is not a running python process. That last line
replaces the plan's "no automatic stale-lock recovery" for runs driven by the
wrapper; `--no-lock-recovery` restores it. The runner files are not touched.

```powershell
# start detached (survives the terminal or editor closing)
powershell -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath .venv\Scripts\python.exe -ArgumentList '-B','-X','utf8','tools\retrieval_harness_keepalive.py','start','--run','weights-cross-v2','--workers','4','--runner','tools\retrieval_harness_fast.py' -RedirectStandardOutput output\research\retrieval-harness-runs\weights-cross-v2\keepalive.out -RedirectStandardError output\research\retrieval-harness-runs\weights-cross-v2\keepalive.err"
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness_keepalive.py show --run weights-cross-v2
.venv\Scripts\python.exe -B -X utf8 tools\retrieval_harness_keepalive.py stop --run weights-cross-v2
```

`stop` writes a STOP file; the wrapper sends Ctrl-Break, the runner's own
finally-block releases the lock, and the next start resumes. A closed lid is a
power-policy matter the wrapper cannot override. Tests:
`test/tests/test_retrieval_harness_keepalive.py` (run with `PYTHONPATH=tools`).

## The grouped runner (2026-09-22)

`tools/retrieval_harness_fast.py` computes the same experiments with one shard
per (case, match, topology, graph_join) family: every description/scope/recovery
policy of the family and every coefficient vector in one pass
(`tools/facet_weighted_fast.py`). It is exact, not approximate: the per-policy
runner's own depth cache is keyed without scope and recovery, three of the four
description settings rank the same bare scores, and the delivered order is a
total order of which `cut` reads at most 109 positions, so the first 128 are
sorted and the rest never touched. `init` freezes the same inputs plus both new
files; `gate --run NAME --against OLD` recomputes every policy of every family
on one area case and one no-area case through `weighted_retrieve` and every
shard the per-policy run OLD has completed, and raises on any metric that
differs (NaN equal to NaN). Shards: 4,750 for the weights cross instead of
152,000. Its runs are read only by this file's `report`; the per-policy runner
and its earlier runs are unchanged and still verify. Measured before the
gate: 8.5–11 s per family of 32 policies against 51–62 s extrapolated for the
per-policy path on the same work, both under load.

## Specification and extension points

The examples are JSON:

- `case_ids`: optional list of numeric-capture IDs; omitted means all 95 saved
  successes. Five original interpreter failures remain excluded and reported.
- `policy_filters`: factor names mapped to allowed-value arrays. Omitted factors
  retain all values present in `facet_retrieval_lab.policies()`.
- Alternatively, `policies`: an explicit list of policy objects.
- `coefficients`: arrays in **topic, temporal, why, activity, concreteness** order.
  Values must be finite, nonnegative and not all zero.
- Alternatively, `coefficient_grid: "recorded_509"` loads the frozen weight grid.
  Omit both to use `[1, 0.25, 0.25, 0.25, 0.25]`.

Use `tools/facet_retrieval_lab.py` for factors, construction enumeration,
`schedule`, `Lab.retrieve`, and post-delivery `Lab.evaluate`.
`test/artefact/facet_operator_matrix.py` constructs the numerical score families.
`tools/facet_weighted_lab.py` applies coefficient overrides with isolated caches.
`tools/retrieval_harness.py` is the new resumable experiment runner.

The historical matrix and weight producers write to frozen, completed folders;
**do not rerun them as a continuation command**. Their results remain available
through the combined leaderboard. New named experiments are reported by the new
CLI; they are **not automatically merged into the existing browser leaderboard**.
Their policies and coefficients can be applied with the browser's existing
controls or `POST /api/replay`.

## HTTP interface

- `GET /api/status`: cases and allowed factors.
- `GET /api/leaderboard?metric=recall_id&subset=all`: completed historical rankings.
  Metric may also be `precision_id` or `f1_id`; subset may be `topic_present` or
  `topic_largest`.
- `POST /api/replay`: JSON with `case_id`, `policy`, `coefficients`, and optional
  `compare_policy` / `compare_coefficients`. Returns numerical scores, ranks,
  source-ID pointers and delivery movements.

Ranking never receives gold labels. Gold source IDs are joined after ordering
and the **72,000-character** serving cut. Partial boundary chunks do not earn
new source-ID credit. These scores measure reference source-ID membership, not
generated-answer quality or exhaustive semantic relevance. Per-query winners
chosen using gold are diagnostic, not a deployable query-time selector.

## State and required local assets

The historical union contains 11,764 policy/weight settings across 95 cases.
Best fixed observed recall: 50.99712%; best with topic a largest coefficient:
50.95510%; gold-selected per-query observed recall: 74.04507%. These are reused
data, not independent validation or a proven optimum.

Keep these directories when moving to another machine or worktree:

- `output/research/2026-09-21-facet-validity/route_snapshot/`
- `output/research/2026-09-22-structural-landings/`
- `output/research/2026-09-22-gold-source-trace/`
- `output/research/2026-09-22-retrieval-matrix/` (inputs and completed experiments)
- The current `prod/`, `test/`, `tools/`, and `examples/retrieval-harness/` sources.

The current local `.venv` is verified. `prod/requirements.txt` is provisional;
do not claim a clean-machine install is verified. A new run's `input_sha256`
manifest enumerates its exact file dependencies using absolute paths. Resume
in the same checkout path and Python/NumPy versions; after relocation initialize
a new run rather than editing a sealed plan. Local caches can include
benchmark or source text: agents should inspect IDs, numbers and graph pointers,
not print questions, reference answers, generated answers or source bodies.

Further context: `docs/2026-09-22-live-retrieval-matrix.md`,
`docs/2026-09-22-facet-retrieval-plan.md`, and
`docs/2026-09-22-facet-pair-kind-validity.md`. The broader facet measurement
investigation remains open; finishing a grid does not settle it.

## Verification performed on 2026-09-22

`handoff-verification-20260922-v2` completed the eight-delivery example. One shard
ran first; resumption added exactly the remaining three. Resuming the completed
run produced zero new shards and preserved every shard hash and modification
time. All four default-weight cells match the historical matrix. The partial
report correctly had no eligible rankings before both cases were complete.
Eight tests in `test/tests/test_retrieval_harness.py` pass for locking, corrupt
shards, changed inputs, partial report populations, grid loading and path safety.

The earlier `handoff-verification-20260922` folder records a failed check against
historical ordering and has no completed shards. That assertion was corrected
to the same current-helper parity contract used by the verified matrix batch;
the successful v2 run uses the corrected, separately hashed runner. Neither
folder is the large weight-cross experiment.

## Paste this into Claude Code or Cursor

> Work in C:\Coding\exjobbet\GRAG-Job. Read docs/RETRIEVAL-HARNESS.md and inspect
> tools/retrieval_harness.py. Continue the cached retrieval-construction experiments
> with the existing .venv and frozen Volmax numeric inputs. Verify the small smoke
> and resume behavior, then use a distinct named run for the remaining specified
> combinations. Preserve completed historical runs and source hashes; no DB writes
> or new model calls are needed. Keep benchmark/source text out of agent output.
> Report highest fixed settings and their tested coverage, distinguish gold-selected
> per-question potential, and never describe the finite grid as all possible designs.

No particular agent plugin or skill is required: shell access to this checkout
and Python environment is sufficient.
