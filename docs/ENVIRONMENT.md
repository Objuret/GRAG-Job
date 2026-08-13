# ENVIRONMENT

Machine-specific facts for the two machines that work this repo. Everything here is
about a machine, not about the design: paths, versions, start recipes, and the traps
each box has. Design lives in `docs/canon/` and `v3/README.md`; results live in
`v3/output/`.

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

### Python

VS Code auto-activates the repo `.venv` in every terminal, so the user's `python` is
that venv. It is healthy: Python 3.12.7, ragas 0.4.3, neo4j 6.2.0, and
`.venv\Scripts\python.exe -m pytest artefact/tests` from `v3/` passes 36/36.

The one gap is graphify: it is not installed in `.venv`, only in miniconda. So
`python refresh_graph.py` needs the miniconda interpreter
(`C:\Users\jocke\miniconda3\python.exe refresh_graph.py`) while everything else in `v3/`
runs on the repo venv.

`.vscode/settings.json:2` pins `python.defaultInterpreterPath` to
`A:/exjobbet/repo/.venv/Scripts/python.exe` — the **desktop** path. There is no `A:` drive
on this machine, so that pin resolves to nothing here and VS Code falls back to whatever
interpreter it can find. Point it at the laptop `.venv` before trusting the auto-activation
above.

`v3/requirements.txt` here is a laptop reconstruction (ragas 0.4.3). The authoritative
version record is the desktop's `A:\exjobbet\repo\.venv`; judged RAGAS metrics differ
across ragas versions, so eval comparability follows the desktop stack (thesis-era
ragas 0.2.x). Retrace owed on the desktop:
`.venv\Scripts\python.exe -m pip freeze > v3\requirements.txt`, then commit.

**Never wipe an env directory without freezing its metadata first** — site-packages
metadata is the only record of the versions a past run used.

### Neo4j

Runs locally: Neo4j Desktop 2 instance "herb" at
`~\.Neo4jDesktop2\Data\dbmss\dbms-7863c729-b4ea-477c-9755-a06a0f9dcbfc`. **Auth is
enabled** — that instance's `conf\neo4j.conf`:31 carries
`dbms.security.auth_enabled=true`, and `v3/pipelines/artefact_v1.py`:522-531 raises
`NEO4J_PASSWORD is not set` before it opens a driver. The password lives in `v3/.env`
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

`herb-eval` is loaded from the repo's git-lfs dump (`v3/artefact/data/herb-eval.dump`):
4,869 chunks, 19,716 tags, 67,913 HAS_TAG edges, `tag_emb` + `chunk_desc_emb` +
`chunk_fulltext` indexes, zero oracle chunks, single run_id `pilot_full_herb`.

### graphify

graphify 0.8.39 is installed (miniconda Scripts); `python refresh_graph.py` runs on
this machine with the miniconda interpreter.

**The distribution is named `graphifyy`, not `graphify`** — the import package and the
console script are `graphify`, the PyPI name has two y's. Consequences when checking the
version: `pip show graphify` reports "Package(s) not found" (use `pip show graphifyy`),
and `graphify.__version__` raises `AttributeError: module 'graphify' has no attribute
'__version__'`. Only the CLI answers: `graphify --version` → `graphify 0.8.39`.

`docs/handoff` does not exist here, so the scan notes it missing —
harmless. Doc extractions go to the semantic cache via
`graphify.cache.save_cached(path, {nodes, edges}, root=REPO, kind="semantic")`;
mirror the node/edge schema of existing entries in `graphify-out/cache/semantic/`.

### NIM

Working key in `v3/.env`. The hosted catalog rotates — a model id that 410s has been
renamed (`z-ai/glm-5.1` → `z-ai/glm-5.2`); check `GET /v1/models` when one errors.
`qwen3.5-397b` queues hard; calls need the 480s timeouts already in the code.

### Headless Claude CLI

Binary at `C:\Users\jocke\.local\bin\claude.exe` — **not on PATH** in agent tool shells,
so call it by full path. `v3/nim.py`:168 handles this:
`_CLAUDE_EXE = shutil.which("claude") or ~/.local/bin/claude.exe`. The claude lane lives
entirely in `nim.py`; `v3/eval/ragas.py`'s own `which` calls are for the other two
subscription CLIs — codex (`:170`) and gemini (`:176`, falling back to the npm shim at
`%APPDATA%\npm\gemini.cmd`).

Invocation: `claude.exe -p "<prompt>" --model <full-slug> --output-format json` —
subscription-billed, the RAGAS `claude-*` judge path. Pass the full slug, not an alias; see
below.

`--json-schema '<schema>'` enforces a JSON Schema on the response, so the generator's
`{"answer": str}` contract and the judge verdict can both be schema-enforced. No
temperature flag exists; reproducibility is this path's one real gap versus NIM.

**Aliases are for typing at the CLI by hand — never pass one through the repo.**
`v3/nim.py`:249 routes a chat call to the claude lane only when the model string
`startswith("claude")`, and every call site in `v3/` passes a full slug
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
re-measured since, and no judge run in `v3/output/` persisted timing to check it against
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
carries `v3/data/** -text`. If hash mismatches appear, suspect `core.autocrlf=true`
re-smudging; restore via `git cat-file blob` writes.

---

## Desktop — `A:\exjobbet\repo`

`.venv` here is the canonical record of the versions the June/July runs used, and the
stack eval comparability follows.

Raw data storage is `A:\exjobbet\data\raw` — never written to; the repo copy is the
working one.
