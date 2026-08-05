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

### Python

VS Code auto-activates the repo `.venv` in every terminal, so the user's `python` is
that venv. When it is broken, commands silently do nothing — give full-path commands
(`C:\Users\jocke\miniconda3\python.exe …`) until it is fixed. Tests run with miniconda
python from `v3/`.

`v3/requirements.txt` here is a laptop reconstruction (ragas 0.4.3). The authoritative
version record is the desktop's `A:\exjobbet\repo\.venv`; judged RAGAS metrics differ
across ragas versions, so eval comparability follows the desktop stack (thesis-era
ragas 0.2.x). Retrace owed on the desktop:
`.venv\Scripts\python.exe -m pip freeze > v3\requirements.txt`, then commit.

**Never wipe an env directory without freezing its metadata first** — site-packages
metadata is the only record of the versions a past run used.

### Neo4j

Runs locally: Neo4j Desktop 2 instance "herb" at
`~\.Neo4jDesktop2\Data\dbmss\dbms-7863c729-b4ea-477c-9755-a06a0f9dcbfc`, auth DISABLED
at the user's direction (localhost-only dev DB). Check port 7687 at session start;
start it before any `artefact_v1` work.

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

`graphify` 0.8.39 is installed (miniconda Scripts); `python refresh_graph.py` runs on
this machine. `docs/handoff` does not exist here, so the scan notes it missing —
harmless. Doc extractions go to the semantic cache via
`graphify.cache.save_cached(path, {nodes, edges}, root=REPO, kind="semantic")`;
mirror the node/edge schema of existing entries in `graphify-out/cache/semantic/`.

### NIM

Working key in `v3/.env`. The hosted catalog rotates — a model id that 410s has been
renamed (`z-ai/glm-5.1` → `z-ai/glm-5.2`); check `GET /v1/models` when one errors.
`qwen3.5-397b` queues hard; calls need the 480s timeouts already in the code.

### Headless Claude CLI

Binary at `C:\Users\jocke\.local\bin\claude.exe` — **not on PATH** in agent tool shells,
so call it by full path. `v3/eval/ragas.py` handles this
(`shutil.which("claude") or ~/.local/bin/claude.exe`).

Invocation: `claude.exe -p "<prompt>" --model <alias> --output-format json` —
subscription-billed, the RAGAS `claude-*` judge path.

`--json-schema '<schema>'` enforces a JSON Schema on the response, so the generator's
`{"answer": str}` contract and the judge verdict can both be schema-enforced. No
temperature flag exists; reproducibility is this path's one real gap versus NIM.

Aliases: `haiku` → claude-haiku-4-5-20251001 (200k ctx / 32k out) · `sonnet` →
claude-sonnet-5 · `opus` → claude-opus-4-8 · `fable` → claude-fable-5 (1M ctx / 64k out
each).

Two traps: `--bare` skips keychain reads and fails with "Not logged in"; and headless
reads stdin, so redirect it (`< /dev/null`) to avoid a 3s stall.

### State-transfer docs

They sit **flat** under the OneDrive additional working directory —
`C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\*.md` — not
nested under `docs/state/` / `docs/handoff/` the way prose paths name them. When a doc
is named `docs/state/<file>.md`, look for `<file>.md` directly in that folder. The
newest-dated doc is the safer first read.

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
