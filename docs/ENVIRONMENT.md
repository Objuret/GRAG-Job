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
`NEO4J_PASSWORD is not set` before it opens a driver. The password lives in `.env` at the repo root;
`NEO4J_URI` and `NEO4J_USER` default to
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
so call it by full path. `prod/harness/chat.py` handles this:
`_CLAUDE_EXE = shutil.which("claude") or ~/.local/bin/claude.exe`. The chat lane lives
entirely in `chat.py` — it is the only model lane since the hosted NIM lane was purged on
2026-09-07 at his word; `prod/eval/ragas.py`'s own `which` calls are for the other two
subscription CLIs — codex (`:170`) and gemini (`:176`, falling back to the npm shim at
`%APPDATA%\npm\gemini.cmd`).

Invocation: `claude.exe -p --model <full-slug> --output-format json --tools "" --safe-mode
--system-prompt <text, or empty>`, the prompt on stdin as UTF-8 bytes — subscription-billed,
the RAGAS `claude-*` judge path too. Pass the full slug, not an alias; see below.

`--json-schema '<schema>'` enforces a JSON Schema on the response (the generator's
`{"answer": str}` contract). No temperature flag exists; a temperature reaches the request
only through `CLAUDE_CODE_EXTRA_BODY`, and only `claude-haiku-4-5` with thinking off takes one
(`claude-sonnet-5` answers 400 to any).

**Aliases are for typing at the CLI by hand — never pass one through the repo.**
`prod/harness/chat.py` accepts a chat call only when the model string
`startswith("claude")`, and every call site passes a full slug
(`claude-haiku-4-5-20251001` is the default of `eval/ragas.py` · `JUDGE_MODEL` since
2026-10-08). A bare `haiku` fails that test and is refused out loud by `chat.post`. The same
applies to anything handed to `--judge` or `--generator`.

The alias→slug mapping the CLI itself uses: `haiku` → claude-haiku-4-5-20251001 (200k ctx
/ 32k out) · `sonnet` → claude-sonnet-5 · `opus` → claude-opus-4-8 · `fable` →
claude-fable-5 (1M ctx / 64k out each). UNVERIFIED — recorded from a past session, not
re-checked against the CLI, and nothing in the repo reads it. Checked 2026-10-08 for one of
them: in the CLI's own transcripts of the lane every call made as `claude-haiku-4-5`, on every
day since 2026-09-08, was answered by `claude-haiku-4-5-20251001`.

Two traps: `--bare` skips keychain reads and fails with "Not logged in"; and headless
reads stdin, so redirect it (`< /dev/null`) to avoid a 3s stall.

**Since 2026-10-05 the lane runs with `--safe-mode`** (CLI 2.1.212 help: all customizations —
CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents — disabled; auth and
model selection work normally) beside `--tools ""` and `--system-prompt`. Without it a headless
call loads the user-level `~/.claude/CLAUDE.md`, the plugins and the MCP servers of this machine:
a querytagger prompt of 3,981 characters counted 24,516 input tokens and came back as a request
for `mempalace_search`; with the flag the same prompt counted 1,093 input tokens and returned
its JSON. `MEMPALACE_HOOKS_AUTO_SAVE=false` is still set on the call.

**Since 2026-10-08 the lane also sets, per call** (`chat.call_settings`; each was seen in a
request the CLI logged, `docs/2026-10-08-model-calls-found-and-fixed.md`):
`CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` (without it the whole prompt goes a second time, to
Haiku, for a session title) · `CLAUDE_CODE_ATTRIBUTION_HEADER=0` (no billing line in the system
prompt) · `--system-prompt` always, empty when the call has none (without the flag Claude Code's
own system prompt goes along, about 15,400 characters) · `--effort <level>` when the caller
names one, else `CLAUDE_CODE_EFFORT_LEVEL=auto` so none is sent (`--safe-mode` does not skip
`~/.claude/settings.json`, and its `effortLevel` went along on the answer calls until then) ·
`MAX_THINKING_TOKENS=0`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS` and, for Haiku, a temperature through
`CLAUDE_CODE_EXTRA_BODY` on a call that asks for thinking off. What the CLI still adds by
itself: the line "You are a Claude agent, built on Anthropic's Claude Agent SDK." first in the
system prompt, and a `<system-reminder>` block in front of the prompt with the e-mail address
of the login stored in `~/.claude.json` and the day's date. The date has no switch.

**Since 2026-10-09 the lane logs in by itself:** every call runs with `CLAUDE_CONFIG_DIR` set to
`~/.claude-herb-lane` and the `CLAUDE_CODE_OAUTH_TOKEN` of the environment (`.env` supplies it;
`claude setup-token` makes one). The CLI then has no stored login to read an e-mail address
from and reads no settings file of the user's, so the block in front of the prompt holds the
date alone. A call without the token is refused, so **a machine that is to make model calls
needs the token in its `.env`**. The CLI's own transcripts of the lane's calls land under
`~/.claude-herb-lane/projects/` from then on (the earlier ones stay under `~/.claude/projects/`);
`settings.json` in that folder keeps them (`cleanupPeriodDays` 36500).

**Seeing what the CLI really sends:** `CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_LOGS_EXPORTER=console
OTEL_METRICS_EXPORTER=none OTEL_TRACES_EXPORTER=none OTEL_LOG_RAW_API_BODIES=file:<dir>` writes
one `<uuid>.request.json` per request into `<dir>`. The files hold the account's ids and e-mail
address. The CLI also keeps its own transcript of every lane call under
`~/.claude/projects/C--Users-jocke-AppData-Local-Temp-herb-claude-lane/`; those hold gold.

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

**Reached from the laptop over SSH since 2026-09-15:** `ssh djuret@192.168.50.253` (OpenSSH server
installed via winget, port 22 opened in the firewall, the laptop's public key
`C:\Users\jocke\.ssh\id_ed25519.pub` in `C:\ProgramData\ssh\administrators_authorized_keys`,
ACL set with the SIDs `*S-1-5-32-544` / `*S-1-5-18` — the Swedish Windows has no group named
"Administrators"). The desktop account has no Windows password, so password SSH is out.
**GPU:** GTX 1080 Ti, 11 GB, driver 581.57; the desktop venv's torch is `2.6.0+cu124` with
`sm_61` in its arch list, so Pascal runs. Load fp16 checkpoints as `dtype=torch.float32`
(Pascal has no fast fp16; `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` measured 501 pairs/s
at batch 128 in fp32 vs 17 on the laptop CPU). **Claude CLI over SSH does not work:** the
CLI (2.1.201) is installed and `~/.claude.json` carries the account, but the OAuth credential
sits in Windows Credential Manager, which a key-authenticated SSH session cannot unlock —
headless calls answer "Please run /login". A scheduled task inside the interactive session
would carry the credential; the agent sandbox refuses to create one. So over SSH the desktop is
a compute box (GPU, CPU), not a model lane, until a token is made interactively there.
No spaCy in the desktop venv; the repo there sits on an old branch — ship the files a job
needs with `scp`, do not rely on the desktop checkout.
**Away from home the desktop is unreachable** (private LAN address; no VPN, no port forward as of
2026-09-15) — a Tailscale install on both machines would fix that for good; Chrome Remote
Desktop on Djuret would let him install it from anywhere. **Colab as the stand-in GPU:** a free
T4 ran the facet reader at 210–295 pairs/s (fp32, batch 256) against the laptop CPU's 14–18
(i7-1360P, 16 threads at 100%); recipe in `state-transfer/GRAG-Job/colab/` (notebook +
gzipped pairs; the cell writes `scores_colab.jsonl` line by line, so a dead runtime loses
nothing scored). The two produced identical values to 1e-6 on 21,632 shared pairs. The
laptop's 16 GB holds 8 concurrent claude CLI workers; 30 exhausted the paging file. The desktop has 32 GB — his 2026-09-17: *"desktop can easily do twice the amount the laptop can, laptop only has 16gb ram, pc has 32"* — so about 16 workers there. **Claude calls on the desktop over SSH work since 2026-09-17:** the long-lived token from `claude setup-token` sits in the laptop's `.env` as `claude_code_auth_token` and is passed per run as the `CLAUDE_CODE_OAUTH_TOKEN` environment variable; tested with claude-haiku-4-5 and with `--model claude-opus-5 --effort high`. The desktop CLI was updated the same day with `npm install -g @anthropic-ai/claude-code@latest`, 2.1.201 → 2.1.274, the laptop's version. The Credential Manager explanation above is not the cause that was found on 09-17: the desktop's `.claude/.credentials.json` had been rewritten 2026-09-15 05:23 with no refresh token and expiry 0, a logged-out state. On the laptop `claude` is not on PATH; the executable is `.local/bin/claude.exe` under the user profile.
 **The desktop's `claude` on PATH is npm's `claude.cmd` shim (2026-09-18):** a `.cmd` runs
through cmd.exe, which cuts an argv element at its first newline, so a multi-line
`--system-prompt` reached the model as its first line only — Haiku answered a JSON-only prompt in
markdown on every try, on 2.1.274 and on 2.1.212 alike (`A:\exjobbet\tmp\argtest.py`:
`ARGS=[-p --system-prompt "line one]`). `prod/harness/chat.py` now resolves a `.cmd` shim to the
native `node_modules\@anthropic-ai\claude-code\bin\claude.exe` beside it and spawns that; the
laptop path (`~/.local/bin/claude.exe`, nothing on PATH) is unchanged. The desktop CLI is pinned to
2.1.212, the laptop's version, so the two machines are one lane (`npm install -g
@anthropic-ai/claude-code@2.1.212`).

**MemPalace (2026-10-04), his *"i want mempalace to be allencompassing here"*:** version 3.10.0, a
user install in the system Python 3.12 (`pip install --user mempalace` with
`C:\Program Files\Python312\python.exe`; executables in
`%APPDATA%\Python\Python312\Scripts`, on the user PATH). One palace for every project at
`C:\Users\jocke\.config\mempalace\palace` (ChromaDB; wings per project: `grag-job`, `arc`,
`neural-nursery`, `new-mem-order`, `bandelview`, `misc`, `thesis`; hook-filed sessions land in
`sessions`, hard-coded in mempalace). The MCP server is registered at user scope
(`claude mcp add --scope user mempalace -- …\mempalace-mcp.exe`), so every session in every
project can search it — **nothing with gold in it goes in** (his 2026-08-02 rule): not `data\`,
not `output\`, not the headless harness lane (`…Temp-herb-claude-lane`, 12,107 tagger/judge
calls), not `~\.gemini\tmp` (the July Gemini judge lane). **The MemPalace Claude Code plugin is installed
at user scope (his 2026-10-04 "the plugin sounds fucking great"; `claude plugin marketplace add
MemPalace/mempalace`, `claude plugin install --scope user mempalace`, plugin 3.11.0 — the pip
package must be kept at the same version):** it brings the MCP server, `/mempalace:*` commands,
and the Stop (silent save every 15 counted messages), SessionEnd and PreCompact hooks; the
hand-made PreCompact hook in `~/.claude/settings.json` was removed the same day so nothing files
twice. The plugin's hooks are user-wide, so they fire on the harness's headless `claude -p` calls
too; `prod/harness/chat.py` therefore runs those calls with `MEMPALACE_HOOKS_AUTO_SAVE=false` in
the environment, which mempalace's own hooks honour as "pass through, save nothing". The hook
scripts resolve Python through `MEMPAL_PYTHON`, set as a user environment variable to
`C:\Program Files\Python312\python.exe` (a bare `python3` on this machine is the Store stub).
The same repository clone (`~\.claude\plugins\marketplaces\mempalace`) carries the Codex plugin
(`codex plugin marketplace add MemPalace/mempalace`, `codex plugin add mempalace@mempalace`), the
Cursor plugin (a junction at `~\.cursor\plugins\local\mempalace` plus `hooks/cursor/install.sh
--scope user --variant full`) and the Antigravity installer (`hooks/antigravity/install.sh`). The backlog goes in with
`C:\Users\jocke\mempalace_ingest_all.ps1` (re-runnable; a file already filed is skipped by path
and mtime; retries on the palace lock). The auto-mode classifier refused `mempalace mine` from an
agent shell and refused to write `cleanupPeriodDays` into his settings; he runs both himself.
**Claude Code deletes transcripts after 30 days** unless `"cleanupPeriodDays"` is set in
`~/.claude/settings.json` — on 2026-10-04 the oldest surviving laptop GRAG transcript was from
09-04; the typed turns before that survive only in `docs/canon/raw/user_turns_all.jsonl`. Codex
rollouts (`~\.codex\sessions`, Desktop/VS Code format) and Cursor chats (`state.vscdb`) have no
mempalace reader as of 3.10.0.

**The last conversation into every new session (2026-10-04), his *"what i DO want to do, is
literally continue the "same conversation""*:** the palace cannot say what was said last (its
`since`/`before` compare filing time, and the whole backlog was filed on one day), so the resume
is a print, not a search: `tools/last_turns.py` prints his last turns and the answer each one got
from the session in which he typed last (the eight most recently modified transcripts are read
and ordered by his last typed turn — a file's mtime moves without him), verbatim, tool calls and
results left out, human turns filtered by `canon_extract`'s rules, with an index of the other
recent sessions. The repo-local `.claude/settings.local.json` (gitignored) runs it as a
SessionStart hook with the venv python on `startup` and `compact` (on compact: the session's own
tail, the part the summary dropped); on `resume` and `clear` nothing. Claude Code caps a hook's
stdout at 10,000 characters and keeps the front past that, so the hook prints at most 9,000.
Project scope on purpose: a user-level hook would fire on every headless `claude -p` call of the
harness (cwd `%TEMP%\herb-claude-lane`). Tested 2026-10-04 with synthetic hook input (startup,
resume, compact, bad JSON: exit 0 each, 0.6–0.7 s); not yet seen in a real new VS Code session.
**Dates in the palace (2026-10-04, his *"why dont you just go back and correct the dates to match
reality on everything?"*):** mempalace stamps every drawer with the mining clock (`filed_at`) and
the transcript file's last timestamp (`authored_at`), and its date filters read `filed_at`.
`tools/palace_dates.py` re-dates every mined drawer to when its content was said or written
(convos: the turn's own timestamp, by a forward walk of the transcript in chunk order; sweep: the
message's timestamp; documents: mempalace's own `content_date`), into both fields, keeping the
mining clock as `mined_at`; metadata only, idempotent, dry run by default, `--apply` writes; the
ingest script runs it last. It needs the palace lock, so it waits for the Claude sessions to be
closed. First applied by him 2026-10-04 (dry run before it: 74,337 drawers, 19,924 exchanges
to their turn's timestamp, 697 unmatched kept, 52,442 document chunks to their content date —
41,475 of those by file mtime, the only date those files carry). Diary and hand-filed drawers are left alone. Re-mined files (a changed transcript, the
PreCompact hook) come back dated by the mining clock until the next run.


`.venv` here is the canonical record of the versions the June/July runs used, and the
stack eval comparability follows.

Raw data storage is `A:\exjobbet\data\raw` — never written to; the repo copy is the
working one.
