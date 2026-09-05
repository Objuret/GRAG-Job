# ENVIRONMENT

Machine-specific facts for the two machines that work this repo. Everything here is
about a machine, not about the design: paths, versions, start recipes, and the traps
each box has. Results live in `output/`.

## The two machines

| | desktop | laptop |
|---|---|---|
| name | Djuret | — |
| repo | `A:\exjobbet\repo` | `C:\Coding\exjobbet\GRAG-Job` |
| commits authored | Objuret | Joakim Wikman |

---

## Laptop — `C:\Coding\exjobbet\GRAG-Job`

### Background agents and the lid

A background agent that reports "stalled: no progress for 600s" has hit a closed laptop,
not a fault of its own. The watchdog fires on the suspend, and the agent's scope, prompt
and tooling had nothing to do with it. Relaunch it unchanged — never rescope it, never
trim its brief, and never treat the stall as evidence the task was too large.

### The user's terminal is bash

He runs scripts himself in a bash prompt with conda active (`$ ` prompt, `(base)`), not
PowerShell. Hand him bash syntax: an environment variable goes inline in front of the
command, `NAME=value python ...`. `$env:NAME = "value"` is PowerShell and sets nothing
there, so a command written that way runs against the wrong defaults and fails deep inside
the pipeline.

### Running an arm

The current arms — `artefact_v2`, `artefact_volmax`, `artefact_graph` — default to
`herb-eval-volmax` and need no database on the command line:

```bash
cd /c/Coding/exjobbet/GRAG-Job
python prod/run.py --arm artefact_v2 --set 10smoke --workers 30
```

`artefact_v1` and `artefact_v1_det` default to `herb-eval`, which carries no `Person`
nodes — the arm refuses to start there whenever the person path is on — so those two
name their database inline:

```bash
NEO4J_DATABASE=herb-eval-v2 python prod/run.py --arm artefact_v1 --set 10smoke --workers 30
```

With neither `-k` nor `--char-budget`, the depth is the 72,000-character budget and the run
files under `output/k=chars/`. `--workers` puts that many judged cells in flight at once;
at the default of 1 the judge runs one call at a time and a ten-question run takes about
thirty-five minutes.

### Python

VS Code auto-activates the repo `.venv` in every terminal, so the user's `python` is
that venv. It is healthy: Python 3.12.7, ragas 0.4.3, neo4j 6.2.0, and
`.venv\Scripts\python.exe -m pytest` from the repo root runs every suite (`pytest.ini`).

`.vscode/settings.json:2` pins `python.defaultInterpreterPath` to
`A:/exjobbet/repo/.venv/Scripts/python.exe` — the **desktop** path. There is no `A:` drive
on this machine, so that pin resolves to nothing here and VS Code falls back to whatever
interpreter it can find. Point it at the laptop `.venv` before trusting the auto-activation
above.

`prod/requirements.txt` here is a laptop reconstruction (ragas 0.4.3). The authoritative
version record is the desktop's `A:\exjobbet\repo\.venv`; judged RAGAS metrics differ
across ragas versions, so eval comparability follows the desktop stack (thesis-era
ragas 0.2.x). Retrace owed on the desktop:
`.venv\Scripts\python.exe -m pip freeze > prod\requirements.txt`, then commit.

**Never wipe an env directory without freezing its metadata first** — site-packages
metadata is the only record of the versions a past run used.

### Neo4j

Runs locally: Neo4j Desktop 2 instance "herb" at
`~\.Neo4jDesktop2\Data\dbmss\dbms-7863c729-b4ea-477c-9755-a06a0f9dcbfc`. **Auth is
enabled** — that instance's `conf\neo4j.conf`:31 carries
`dbms.security.auth_enabled=true`, and `test/graph/db.py` raises
`NEO4J_PASSWORD is not set` before it opens a driver. The password lives in `.env` at the repo root
beside `NVIDIA_API_KEY`; `NEO4J_URI` and `NEO4J_USER` default to
`neo4j://localhost:7687` and `neo4j`. Check port 7687 at session start; start it before
any `artefact_v1` work.

Start it **detached** — a plain background task's process tree gets reaped between
turns and takes the server with it. With `JAVA_HOME` set to
`~\.Neo4jDesktop2\Cache\runtime\zulu21.*`:

```powershell
Start-Process <dbms>\bin\neo4j.bat -ArgumentList console -WindowStyle Hidden
```

(redirect stdout/stderr to files; the orphaned java survives).

Three databases are online. All three carry 4,869 chunks, 33 files, one `Source`, the
single `HAS_TAG.run_id` `pilot_full_herb`, and the `tag_emb` + `chunk_desc_emb` +
`chunk_fulltext` + `chunk_content_ft` indexes.

| database | tags | HAS_TAG | entity layer |
|---|---|---|---|
| `herb-eval-volmax` | 16,714 | 62,028 | `Employee` 530, `Customer` 120, `Channel` 302, `Product` 30, `Role` 17, `Company` 10, `Org` 6, `Kind` 6 — reached by lowercase edges: `slack`, `channel`, `product`, `documents`, `meeting_transcripts`, `manages`, `kind` |
| `herb-eval-v2` | 15,605 | 62,443 | `Person` 650, `Employee` 530, `Customer` 120, `Channel` 294, `Product` 30, `Company` 10, `Org` 6 — reached by `INVOLVES` (27,006) and `MENTIONS` (9,632) |
| `herb-eval` | 19,716 | 67,913 | none |

`herb-eval-volmax` is the current graph: the default of `artefact_v2`,
`artefact_volmax` and `artefact_graph`, and where any live read of the graph goes.
`herb-eval-v2` is the only database with `Person` nodes, so the v1 arms run there.
`herb-eval` is the pre-entity build, loaded from the repo's git-lfs dump
(`test/artefact/data/herb-eval.dump`). Zero oracle chunks in all three.

### graphify

graphify 0.8.39 is installed in the repo `.venv` (and in miniconda), so `python -m graphify
query "..."` and `python refresh_graph.py` run on the same interpreter as everything else.

**The distribution is named `graphifyy`, not `graphify`** — the import package and the
console script are `graphify`, the PyPI name has two y's. Consequences when checking the
version: `pip show graphify` reports "Package(s) not found" (use `pip show graphifyy`),
and `graphify.__version__` raises `AttributeError: module 'graphify' has no attribute
'__version__'`. Only the CLI answers: `graphify --version` → `graphify 0.8.39`.

The refresh scans `prod/` and `test/` and extracts from the AST; a full rebuild is a few seconds and
makes no model calls.

### NIM

Working key in `.env` at the repo root. The hosted catalog rotates, and a 410 means one of two things:
the id was renamed (`z-ai/glm-5.1` → `z-ai/glm-5.2`), or the model was retired outright.
Check `GET /v1/models` for the rename, and Hugging Face for the weights — a retired
endpoint does not mean a retired model. `qwen3.5-397b` queues hard; calls need the 480s
timeouts already in the code.

### The embedder — local, not hosted

`nvidia/llama-nemotron-embed-1b-v2` runs in-process from the published weights, pinned to
revision `113abe4acafa848e77ead9c0623205e511932348`, loaded through sentence-transformers
with `trust_remote_code=True` (it ships a custom `LlamaBidirectionalModel`). NVIDIA Open
Model License, commercially usable. The hosted NIM endpoint for it returns 410 — retired
2026-08-25 — and the local weights are the same model, so the graph's vectors, the embed
caches and every past run stay valid.

`.venv` carries `torch` 2.14.0+cpu and `sentence-transformers` 6.0.1 for it. No GPU on this
machine.

The conventions, confirmed by measurement against the graph's own vectors rather than read
off the model card: `input_type="passage"` is the prefix `passage: ` and `input_type="query"`
is `query: `. Against stored `Tag.emb` the passage prefix gives cosine 0.993, the query
prefix 0.44, bare 0.57. Local float32 output sits at cosine 0.987–0.997 (mean 0.993) from
the vectors NIM built, which is serving precision, not a different model. float32 also runs
4.8x faster than the checkpoint's own bfloat16 here and returns unit-norm vectors, which
bfloat16 does not.

Cold model load 40–50 s, warm 15–17 s. Throughput on an idle machine, over real corpus
text of median 55 tokens: **530 ms per text**, and batch size does not matter — 530 / 532 /
523 / 547 / 615 ms per text at batch 1 / 4 / 8 / 16 / 32, vectors bit-identical at every
size. Measure this idle: sweeps taken while agents were running come out up to 3.5x slower
and reverse the ordering, which is how a batch constant ended up justified by noise. Every
gold-100 probe is already cached, so a gold-100 run pays no embedding cost.

### Headless Claude CLI

Binary at `C:\Users\jocke\.local\bin\claude.exe` — **not on PATH** in agent tool shells,
so call it by full path. `prod/harness/nim.py` handles this:
`_CLAUDE_EXE = shutil.which("claude") or ~/.local/bin/claude.exe`. The claude lane lives
entirely in `nim.py`; `prod/eval/ragas.py`'s own `which` calls are for the other two
subscription CLIs — codex (`:170`) and gemini (`:176`, falling back to the npm shim at
`%APPDATA%\npm\gemini.cmd`).

Invocation: `claude.exe -p "<prompt>" --model <full-slug> --output-format json` —
subscription-billed, the RAGAS `claude-*` judge path. Pass the full slug, not an alias; see
below.

`--json-schema '<schema>'` enforces a JSON Schema on the response, so the generator's
`{"answer": str}` contract and the judge verdict can both be schema-enforced. No
temperature flag exists; reproducibility is this path's one real gap versus NIM.

**Aliases are for typing at the CLI by hand — never pass one through the repo.**
`prod/harness/nim.py` routes a chat call to the claude lane only when the model string
`startswith("claude")`, and every call site passes a full slug
(`claude-haiku-4-5` is the default of both `eval/ragas.py` · `JUDGE_MODEL` and
`pipelines/artefact_v1.py` · `INTERPRET_MODEL`). A bare `haiku` fails that test, falls
through to the NIM branch, and dies there as an unknown NIM model id — silently wrong
routing, not a clear error. The same applies to anything handed to `--judge` or
`--generator`.

The alias→slug mapping the CLI itself uses: `haiku` → claude-haiku-4-5-20251001 (200k ctx
/ 32k out) · `sonnet` → claude-sonnet-5 · `opus` → claude-opus-4-8 · `fable` →
claude-fable-5 (1M ctx / 64k out each). UNVERIFIED — recorded from a past session, not
re-checked against the CLI, and nothing in the repo reads it.

Two traps: `--bare` skips keychain reads and fails with "Not logged in"; and headless
reads stdin, so redirect it (`< /dev/null`) to avoid a 3s stall.

Measured throughput, 2026-07-17, haiku: **5.3 s per verdict serial, and 4 verdicts in
6.6 s concurrently.** That is the only latency figure anyone has recorded for this lane,
and it is what a judge-run cost estimate should be built on rather than a guess. Source:
the machine-local `2026-07-17-judge-shootout-rebuilt-artefact-v1-laptop.md`; not
re-measured since, and no judge run in `output/` persisted timing to check it against
(`judge_elapsed_s` is null in every eval manifest).

### State-transfer docs

**Two locations are live, and the OneDrive one is authoritative.**

The full set sits **flat** under the OneDrive additional working directory —
`C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\*.md` — not
nested the way prose paths name them. 11 `.md` files there, plus `_desktop_repo_docs/`
and `_desktop_transcripts/`.

`docs/state/` **also exists** in the working tree and holds 5 of those same files,
byte-identical: `2026-07-20-v1-query-relative-areas.md`,
`2026-07-22-retrieval-literature-sweep.md`,
`2026-07-22-v1-curve-walk-facets-and-cluster-k.md`,
`2026-07-25-combine-clusterk-hybrid-and-judged-eval-usage-burn.md`,
`2026-07-28-audit-absorption-full-revert-corroboration-probe.md`. It is a **stale
subset** — it is missing the two newest (`2026-08-02-benchmark-validity-record.md`,
`2026-08-02-corpus-facts.md`) along with `USER_CANON.md` and the three older docs.

So: when a doc is named `docs/state/<file>.md`, check `docs/state/` first, and fall back
to `<file>.md` directly in the OneDrive folder. Read the newest-dated doc first, and take
the OneDrive copy when only one of the two has it.

### Benchmark data

Must stay byte-exact — the artefact arm hash-verifies raw files. `.gitattributes`
carries `data/** -text`. If hash mismatches appear, suspect `core.autocrlf=true`
re-smudging; restore via `git cat-file blob` writes.

---

## Desktop — `A:\exjobbet\repo`

`.venv` here is the canonical record of the versions the June/July runs used, and the
stack eval comparability follows.

Raw data storage is `A:\exjobbet\data\raw` — never written to; the repo copy is the
working one.
