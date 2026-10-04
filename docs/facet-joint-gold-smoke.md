# Joint-facet standard 10smoke and RAGAS

`tools/facet_joint_gold_smoke.py` prepares an immutable plan, then runs the
registered `artefact_facet_joint` arm through the existing `prod/run.py` harness.
It preserves the standard 10smoke set and all 14 selected RAGAS metrics. The
retrieval uses a frozen Volmax snapshot; it does not claim a live graph run.
Do not tune the retrieval from questions, gold, answers or per-question scores.

Prepare after the adapter and its review/tests are complete:

```powershell
.venv\Scripts\python.exe -B -X utf8 tools/facet_joint_gold_smoke.py --prepare
```

Preparation is also the default. It imports no arm or evaluation stack, reads
no benchmark records and makes no model calls. It refuses until the arm exists,
is registered for character budgets, and declares its static
`SMOKE_PROVENANCE_PATHS` and `SMOKE_MODEL_CONFIG`. It hashes the wrapper, runner,
adapter, declared retrieval code/artifacts, and harness/evaluator Python files.
The plan stores the exact commands, model configuration and its hash, and raw
standard metric names. The new folder is:

```text
output/k=chars/artefact_facet_joint__10smoke__cb72000__<UTC>/
```

Execute the returned prepared folder explicitly:

```powershell
.venv\Scripts\python.exe -B -X utf8 tools/facet_joint_gold_smoke.py --run "<prepared-folder>"
```

The fixed stages are:

```text
prod/run.py --arm artefact_facet_joint --set 10smoke --char-budget 72000 --workers 4 --generator claude-sonnet-5 --no-eval --out <prepared-folder>
prod/run.py --rejudge <prepared-folder> --set 10smoke --judge claude-haiku-4-5 --workers 16
```

The judge receives the same answer folder. Standard `--rejudge` writes to its
sibling `<prepared-folder>__j-claude-haiku-4-5__10smoke`; the wrapper does not
change that convention. No evaluator, metric selection or score transformation
is substituted. Reported means use successful finite values, alongside each
metric's successful, error and missing cell counts.

The second stage starts only when generation exits successfully and the saved
outputs and manifest agree on 10 unique, nonempty answers, zero failures, the
requested arm/generator and 72,000-character budget. This is an explicit
completeness gate required by rejudging the original fixed ten: a partial run
is reported as incomplete without making a substitute question set or silently
evaluating a subset. No phase is automatically retried. Standard model transport
retry behavior inside the unchanged harness is retained.

`started.json` is created exclusively before any child starts. Existing starts,
existing answer/judge outputs, changed commands, or changed frozen inputs cause
refusal. Phase start/completion markers and the final `completed.json` distinguish
a completed process from an interrupted one. Keep the live terminal handle and
poll it; launching this wrapper again is not a resume operation.

Public inspection is limited to `smoke_plan.json`, marker files and
`aggregate_report.json`, plus the wrapper's aggregate-only terminal output.
Reports include phase timing, aggregate counts, all 14 metric means/error counts,
and numeric usage fields available from standard outputs. Usage can be incomplete
when a process fails; missing telemetry is not zero cost.

Treat these paths as private and do not open them in an agent conversation:

- `<prepared-folder>/private/generation.log`: merged child stdout/stderr.
- `<prepared-folder>/private/judge.log`: merged judge stdout/stderr.
- `<prepared-folder>/private/wrapper_error.log`: unexpected wrapper exceptions.
- Standard answer/failure files and all sibling judge per-question result files.
- Adapter private interpreter/query caches declared by the adapter.

The wrapper mechanically reads standard records only to count records and
nonempty answers, accumulate numeric usage and aggregate metric cells. It never
prints questions, gold, answers, contexts, per-question identifiers, raw failures,
judge explanations, or child logs. Unknown metric names are counted as an audit
error without echoing their text. A failed run requires a separate explicit
decision; neither preparation nor execution performs gold-driven repair.
