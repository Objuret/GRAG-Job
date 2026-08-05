# REVIEW_WORKLIST — one row per claim

> **Interpretation, produced 2026-08-04, unreviewed by the user.** This file is a list of things
> to check. It is not a finding, not a verdict, and not evidence for anything. It appears in its
> own list (`W-E58`).

`REVIEW_REGISTER.md` cuts the pile by **file**. This one cuts it by **claim** — the unit that
actually costs something, because a claim is what an agent reads and then enforces. A file is
neither true nor false; a claim is.

**Working this list is governed by `REVIEW_PROTOCOL.md`, which is binding.** Read it first. The
short version: one item at a time, every verdict carries a command and its pasted output, and
no interpretation-tier document — including this one, including `CANON_AUDIT.md` — is ever
evidence.

## Ordering

Rows are ordered by **enforcement power**: how much work a wrong claim misdirects before anyone
notices. Not by how wrong it looks.

| Tier | Surface | Why here | Rows |
|---|---|---|--:|
| 1 | `CLAUDE.md` | Loads every session, for every agent. A wrong line here is read thousands of times. | 50 |
| 2 | The 24 live laptop memory files | Auto-load every session. Same reach as tier 1, less scrutiny. | 70 |
| 3 | The 10 `.claude/agents/*.md` definitions | Become hard rules the instant an agent spawns. The audit found this surface's grounded-to-invented ratio the worst in the repo. | 50 |
| 4 | `v3/README.md` | Carries a `## Decided` heading, which makes every line under it a canon claim. | 28 |
| 5 | Everything else | Inert until someone opens it: `DESIGN.md` + `MODEL_CONTRACTS.md`, the desktop-memory claims, the state docs, the `docs/canon/` documents. | 40 |
| B | Block decisions | The 85 memory copies and the 57 legacy worktree docs are not 142 rows. One row each, proposing a block decision. | 6 |

## Columns

- **id** — stable. Cite it in verdicts.
- **surface** — the file the claim is asserted in. File-level, not the copy of it somewhere else.
  Tiers 1 and 4 cover a single file each, so the surface is carried by the section heading
  (`CLAUDE.md`, `v3/README.md`) instead of repeating in every row; tiers 2, 3, 5 and B name it
  per row, with `file:line` where the line is load-bearing.
- **claim** — quoted verbatim as that surface states it. Where a claim runs long, the operative
  sentence is quoted whole; ellipsis marks removed connective text only, never a qualifier.
- **kind** — **intent** (a claim about what the user wanted) or **state** (a claim about what
  exists, what a number is, what the code does). The distinction decides what can settle it:
  intent is settled only in the corpus, state only in git, code, data or run output.
- **check** — something runnable. A `CQ` corpus search, a `git` command, or a code path with line
  numbers. Never "see the audit".
- **audit prior** — `CANON_AUDIT.md`'s verdict where one exists, **marked as one agent's opinion,
  carrying no weight**. `—` means the audit never covered this claim; it is new to this list.
- **status** — every row starts `unreviewed`. Only the user changes it.

## The `CQ` corpus search

Every intent check below is written as `CQ "<regex>"`. Define it once per session. It prints the
corpus **line number**, the timestamp, and the turn text — the line number is what a verdict
cites.

Bash:

```bash
cd /c/Coding/exjobbet/GRAG-Job
CQ () { python -c "
import json,sys,re
pat=sys.argv[1]; n=0
for i,l in enumerate(open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8'),1):
    d=json.loads(l)
    if re.search(pat,d['text'],re.I):
        n+=1; print('L%d  %s  %s' % (i, d['iso_timestamp'][:16], d['text'][:400].replace(chr(10),' / ')))
print('-> %d hit(s)' % n)
" "$1"; }
```

PowerShell:

```powershell
Set-Location C:\Coding\exjobbet\GRAG-Job
function CQ ($pat) { python -c @"
import json,sys,re
pat=sys.argv[1]; n=0
for i,l in enumerate(open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8'),1):
    d=json.loads(l)
    if re.search(pat,d['text'],re.I):
        n+=1; print('L%d  %s  %s' % (i, d['iso_timestamp'][:16], d['text'][:400].replace(chr(10),' / ')))
print('-> %d hit(s)' % n)
"@ $pat }
```

`rg` is not on the bash PATH on this machine — do not write checks that assume it.

**Zero hits is a real result and must be reported as such.** It is not proof the user never said
it. Read the blackout rule below before converting any zero into a verdict.

## Two things that will bite whoever works this list

**The corpus blackouts.** The corpus is 803 turns, 2026-05-14 → 2026-08-03. Nothing survives
before 05-14, and **05-16 → 05-26** and **05-29 → 06-26** hold zero turns. A claim whose only
support would sit in those windows returns zero hits *by construction*. That is
`cannot-determine`, never `unsupported`.

This is not hypothetical. Two quotes `CANON_AUDIT.md` cites with dates — *"MY WORDS ARE THE
CANON"* (06-25) and *"this is ONLY RAGAS"* (06-25) — return **zero** hits in the corpus, because
06-25 is inside the second blackout. They are `[DOC]` recoveries out of
`raw/desktop_docs_record.md` (agent-written notes of a conversation), presented in the audit
alongside genuine `[CHAT]` quotes with no visual distinction. Several rows below inherit that
problem; the check column says so where it applies.

**The four data files are off limits.** `v3/data/questions.jsonl`, `gold100.jsonl`,
`heldout100.jsonl` and `10smoke.jsonl` are not to be opened — 2026-08-02: *"honestly, you should
not have the questions/gold available to you, there is 0% good that can come out of taht"*
(`CQ "should not have the questions"`). Rows whose natural check would open one are marked
**[user-gated]**: propose the check, do not run it.

---

## Tier 1 — `CLAUDE.md` (50 claims)

Loaded by every agent, every session. 20 of these carry an audit prior; **30 are new to this
list** — the file was rewritten on 2026-08-03, after the audit read it, and the rewrite added a
whole epistemics layer that nothing has checked.

### 1a — The banner and the repo-layout claims

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C01 | "This file is agents' claims about how this project should work, written over months; being written here is not the user's approval of it." | intent | `CQ "just because the text is in the repo\|pretend its canon"` | — | unreviewed |
| W-C02 | "Intent — what was supposed to be built — lives only in the user's own typed turns (`docs/canon/raw/user_turns*`)." | intent | `CQ "everything I HAVE SAID\|things I ACTUALLY SAID"` — then ask whether "only" is the user's word or the agent's | — | unreviewed |
| W-C03 | "State — what exists — lives in the git history and the code, and is evidence of drift from intent, never justification for it." | intent | `CQ "GIT REPO HAS ALL THE FUCKING HISTORY"` | — | unreviewed |
| W-C04 | "`docs/canon/CANON_AUDIT.md` checks 117 prescriptive claims across the repo's instruction surfaces … of which 20 come from this file." | state | Count the rows: `python -c "import re;t=open('docs/canon/CANON_AUDIT.md',encoding='utf-8').read();print(len(re.findall(r'^\| [1-7]\.\d+ ',t,re.M)))"` — then reconcile against the audit's own subtotal table at `CANON_AUDIT.md:45-51` | — | unreviewed |
| W-C05 | "**`v3/`** — the work: a lean HERB evaluation harness … Self-contained." | intent | `CQ "NOT doing the v3 artefact"` → L588, 2026-07-26T23:07 | **[CONTRADICTS-USER]** (1.9) | unreviewed |
| W-C06 | "**`docs/canon/`** — the committed record: what the user specified, how the system was built, and where the repo's own claims diverge from either." | intent | `CQ "filter through every fucking memory\|Search the entire repo for exactly ALL information"` | — | unreviewed |
| W-C07 | "Regenerate the underlying corpus with `tools/canon_extract.py`." | state | `python tools/canon_extract.py --help` then `git log --oneline -- tools/canon_extract.py` | — | unreviewed |

### 1b — Session entry point and trust ordering

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C08 | "**`docs/canon/README.md` — the canon library. Read it before anything else.** It is committed, so it travels with the repo and with every clone." | intent | `git ls-files docs/canon/README.md` (committed?) + `CQ "clean session\|dont fucking bloat a new session"` | — | unreviewed |
| W-C09 | "`docs/canon/USER_CANON.md` — the user's verbatim words, 469 sourced quotes, 2026-05-14 → 2026-08-03." | state | Count quote markers: `python -c "import re;print(len(re.findall(r'\[CHAT\]\|\[DOC\]',open('docs/canon/USER_CANON.md',encoding='utf-8').read())))"` — and check the `[DOC]` share, which is not verbatim user words | — | unreviewed |
| W-C10 | "**Trust ordering:** the user's verbatim words outrank every doc, every memory entry and every agent's output." | intent | `CQ "MY WORDS ARE THE CANON"` → **0 hits** (06-25 sits in the 05-29→06-26 blackout; the audit's citation is a `[DOC]` recovery). Fall back to `CQ "my thoughts defiled\|the origial concepts were mine"` | **[GROUNDED]** (1.3) — cited to a quote absent from the corpus | unreviewed |
| W-C11 | "Where a doc conflicts with the record, the record wins, and the conflict goes to the user as a question — never resolved silently." | intent | `CQ "i will fucking tell you if i want something rewritten"` | — | unreviewed |
| W-C12 | Entry-state-doc pointer: "`docs/state/2026-07-28-audit-absorption-full-revert-corroboration-probe.md` … **Read this first for any artefact_v1 retrieval work.**" | state | `ls docs/state/ 2>&1` then `ls "C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/"*.md` — the docs are flat in OneDrive, not under `docs/state/` | **[STALE]** (1.20 / 7.7) | unreviewed |
| W-C13 | "The corroboration probe it specs has since run: real signal, redundant with description distance …; oracle headroom +0.21 in-territory; the Part-J discriminator remains unfound." | state | The probe's scripts and intermediates are in a session scratchpad, not the repo — `ls v3/output/ \| grep -i corrob`. If nothing on disk reproduces +0.21, this is `cannot-determine` and the memory entry repeating it (W-M52) falls with it | — | unreviewed |
| W-C14 | "**Do not re-derive from DESIGN.md/MODEL_CONTRACTS.md — those are stale.**" | state | `git log -1 --format=%ci -- v3/artefact/DESIGN.md v3/artefact/MODEL_CONTRACTS.md` vs the state doc's date; then diff a specific claim (W-E01…W-E15 are the itemised conflicts) | — | unreviewed |
| W-C15 | "**Persistent memory (auto-loads in Claude Code…):** `C:\Users\Djuret\.claude\projects\a--exjobbet-repo\memory\MEMORY.md`" | state | `ls "C:/Users/Djuret/.claude/projects/a--exjobbet-repo/memory/MEMORY.md"` — that is the **desktop** path and user; the live laptop memory is `C:/Users/jocke/.claude/projects/c--Coding-exjobbet-GRAG-Job/memory/` | — | unreviewed |
| W-C16 | "`docs/handoff/` (frozen). Each is dated and describes its own moment." | state | `ls docs/handoff 2>&1` — `docs/ENVIRONMENT.md` §graphify records this folder as absent on this machine | — | unreviewed |
| W-C17 | "**State doc folder (dated; newest = entry point):** `docs/state/`" | state | Same as W-C12 | **[STALE]** (7.7) | unreviewed |
| W-C18 | "When a newer state doc supersedes the entry point, update line 1 here in the same pass." | intent | `CQ "state doc"` and `CQ "handoff"` — check whether any turn asks for this maintenance rule | — | unreviewed |

### 1c — The graphify rules

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C19 | "**Answering questions about the code:** query the graph FIRST, before grepping — `graphify query "<question>"` …" | intent | `CQ "graphify"` → 3 hits (L70 07-01 "Use graphify in you can"; L345 07-20 "fix graphify then"; L688 07-29 the 25-minute complaint). None asks for graph-before-grep | — | unreviewed |
| W-C20 | "Never per-edit; doc extraction is expensive, so all changed docs ride the same pass." | intent | `CQ "graphify"` → does any turn set a batching cadence? | — | unreviewed |
| W-C21 | "**Refresh the navigation graph at commit time:** run `python refresh_graph.py` … once per commit … It is the ONLY rebuild path (never `graphify --update`). If it prints a worklist, process it before committing." | intent | `CQ "graphify"` → L688 2026-07-29T23:02 is the user asking why this is happening at all: *"so, apparently somewhere i the docs there is something telling you to do this?"* (`CQ "apparently somewhere i the docs"`) | **[AGENT-ORIGIN]** (1.8), ranked #8 | unreviewed |

### 1d — Hard rules

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C22 | "**An agent's own output is not canon:** producing a document, a report or a run does not make its contents decided. A design claim is attributed to the user only when `docs/canon/USER_CANON.md` carries the quote; otherwise it is a proposal, and says so." | intent | `CQ "you literally put shit in writing and pretend its canon"`. **Then the second half separately**: making `USER_CANON.md` — an interpretation-tier document, 469 agent-selected quotes with 115 second-hand `[DOC]` entries — the attribution gate contradicts `docs/canon/README.md`'s own rule that nothing in that tier outranks anything else. Check whether the user asked for a gate at all | — | unreviewed |
| W-C23 | "**Design before build:** no pipeline code until the relevant stage's design is explicitly signed off by the user." | intent | `CQ "i will fucking tell you if i want something rewritten"` and `CQ "STOP then, if nothing needs to fucking change"`. The audit's primary citation (desktop record 06-11, *"all parts are decided upon first"*) is a `[DOC]` recovery in a blackout window | **[GROUNDED]** (1.1) | unreviewed |
| W-C24 | "**Talk to the user in plain spoken English, short answers** — no jargon walls, no spec-sheet dumps." | intent | `CQ "i am not fucking reading pages\|writing too fucking much\|not reading that"` | **[GROUNDED]** (1.2) | unreviewed |
| W-C25 | "Verify claims against the real system/data before asserting." | intent | `CQ "verify\|verified by me"` — note 08-02: *"ok, you do realise \"verified by me\" means YOU verified? and not me?"* | — | unreviewed |
| W-C26 | "**Heed the user's intent — never \"correct\" it with stale context.** … Surface a genuine conflict as a question, not a correction." | intent | `CQ "my thoughts defiled\|bastardizing and forgetting the origins"` → 07-21 | **[GROUNDED]** (1.3) | unreviewed |
| W-C27 | "**Docs track reality:** when a decision closes, update the design doc + memory in the same pass, by removal of dead content, not banners." | intent | `CQ "REMOVE, quarantine, legacy-note"` and `CQ "continously update information"` — both are audit-cited to 06-12, inside the blackout: expect 0 hits and rule `cannot-determine` | **[GROUNDED]** (1.4) | unreviewed |
| W-C28 | "Dated state/handoff docs are frozen — they describe that moment." | intent | `CQ "still true for THAT build"` — audit cites 06-12 (blackout) | **[GROUNDED]** (1.4) | unreviewed |
| W-C29 | "**No historical or defensive comments:** code, docs and commit messages state only the present … Never narrate a past mistake, a change, or a review finding." | intent | `CQ "previously\|no longer\|historical comment"` — the audit grounds the *principle* on desktop record 06-23 (blackout, `[DOC]`) | **[GROUNDED]** on the principle (1.5) | unreviewed |
| W-C30 | "…no \"previously/now\", \"no longer\", \"NOT because\", \"do not factor out\", no review-finding labels." | intent | `CQ "do not factor out"` and `CQ "NOT because"` → expect 0 hits; the audit itself calls the enumerated phrase list agent-authored | **[AGENT-ORIGIN]** on the phrase list (1.5) | unreviewed |
| W-C31 | "**Every runnable shows life instantly and progress continuously** … A silent terminal — or a run buried where the user can't watch it — is a bug, full stop." | intent | `CQ "fucing progress\|permanent understanding of the human need"` → 07-16T08:42; and `CQ "perhaps thats a thing you should have in the .md"` → the user asking for this rule to be written down | **[GROUNDED]** (1.6) | unreviewed |
| W-C32 | "Print the banner before any heavy import …, `flush=True`, and drive the harness progress bars (`v3/progress.py`)." | state | `ls v3/progress.py` and `grep -n "def progress" v3/progress.py` | — | unreviewed |
| W-C33 | "**Critical-review logic changes only:** after changing real logic in `v3/`, run `/critical-review` on the changed file(s) — in the background, one batched review per work burst …" | intent | `CQ "critical.?review"` → **0 hits in 803 turns** (verified). Then `CQ "adversar"` — the user asked for adversarial *panels* on the artefact (07-22, 07-23), which is a different thing | **[AGENT-ORIGIN]** (1.7) | unreviewed |

### 1e — The agent roster section

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C34 | "The main-chat Claude is the orchestrator: it talks to the user and routes every job to a specialist agent; it does no hands-on work itself." | intent | `CQ "always only the orchestrator"` → L455, 2026-07-22T15:36 | **[GROUNDED]** (1.18) | unreviewed |
| W-C35 | "Plain questions get direct conversational answers — no agents, no tool calls." | intent | `CQ "questions get answers\|Me having a fucking opinion"` | **[GROUNDED]** (1.18, bundled) | unreviewed |
| W-C36 | "Agents always run in the background — a foreground agent freezes the conversation." | intent | `CQ "highjacking my conversation"` → 07-29T22:48 | **[GROUNDED]** (1.18, bundled) | unreviewed |
| W-C37 | "Prompts are scoped to the change: a two-line change gets a two-line prompt, never a tree-wide audit unless the user asks for one." | intent | `CQ "DO NOT fucking touch a part i have not asked you about"` → 07-30 | — | unreviewed |
| W-C38 | "Long runs still happen in the user's terminal: agents prepare, the user runs." | intent | `CQ "let ME be the one"` → L173, 2026-07-16T07:40 (verified) | **[GROUNDED]** (1.19) | unreviewed |
| W-C39 | The ten-name routing table (v3-coder … graph-refresher) | intent | `CQ "one code optimization expert\|one for maths algoritms"` → 07-22T15:45, the user itemising the roster. Check name-by-name which of the ten he actually named | **[GROUNDED]** (3.13) | unreviewed |
| W-C40 | "**results-analyst** — reading `v3/output/`, reporting numbers (metric validity binding)." | intent | `CQ "DATA_README\|validity"` — "binding" is the operative word; DATA_README is agent-written | **[AGENT-ORIGIN]** on "binding" (3.5) | unreviewed |

### 1f — The artefact-arm section

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-C41 | "The artefact is the system under test, rebuilt natively in `v3/artefact/`. … The v3 artefact rebuilds from raw natively in `v3/artefact/`" | intent | `CQ "NOT doing the v3 artefact"` → L588 2026-07-26T23:07: *"EVERYTHING i have been TRYING to build for weeks now, have been the actual v1artefact"*. The arm that produces every number is `v3/pipelines/artefact_v1.py` | **[CONTRADICTS-USER]** (1.10), ranked #6 | unreviewed |
| W-C42 | "Its deterministic stages exist and are tested (`python -m pytest artefact/tests` from `v3/`): `scan.py` …, `probe.py` …, `derive_corpus.py` …, `resolver_prototype.py` …" | state | Run it: `cd v3 && python -m pytest artefact/tests` — paste the summary line | — | unreviewed |
| W-C43 | "The graph proper — chunk → tag → facet retrieval — is the unbuilt part; `pipelines/artifact.py` is the arm entry that drives it." | state | `ls v3/pipelines/` → **`artifact.py` does not exist** (verified); `artefact.py`, `artefact_v1.py`, `artefact_v1_det.py`, `hybrid.py`, `lucene.py`, `vector.py` do. `ls v3/artefact/` → `chunk.py`, `tag.py`, `index.py`, `graph_store.py`, `interpreter.py`, `prepass.py` all exist. `git log --diff-filter=D --oneline -- v3/pipelines/artifact.py` | **[STALE]** — factually false at HEAD (1.11) | unreviewed |
| W-C44 | "**The graph spine is closed canon:** `Source → File → Chunk → Tag` are the only nodes. Hard fields are chunk attributes." | intent | `CQ "OTHER RANDOM FUCKING NODES"` and `CQ "just have shit like that as attributes"` — audit cites 06-12 (blackout, `[DOC]`): expect 0 hits, rule `cannot-determine` | **[GROUNDED]** (1.12) | unreviewed |
| W-C45 | "The graph is references into untouched raw source, never copies — never put values, inventories, or mirrors of metadata directories into it." | intent | `CQ "content should never exist in the graph"` → 07-06T10:54 (inside the covered window) | **[GROUNDED]** (1.13) | unreviewed |
| W-C46 | "**The model emits no numbers, ever** (tagger and interpreter)." | intent + state | Intent: `CQ "no numbers\|emits no numbers"`. State: the shipping interpreter contradicts it — `v3/pipelines/artefact_v1.py:645` is the prompt *"Score retrieval tags against five facets (each 0.0-1.0)."* and `:774` raises `f"facet {f!r} of tag {row['t']!r} is not a number"` (verified). The v3 tagger complies: `v3/artefact/tag.py:4` | **[GROUNDED]** as a rule, **[STALE]** as applied (1.14), ranked #9 | unreviewed |
| W-C47 | "The chunk description is dead." | intent + state | Intent: `CQ "chunk.descriptions\|chunk-descriptions"` → 3 hits, incl. **L760, 2026-08-02T09:17**: *"wasnt the plan to cluster the tags weighted by facets in combination with chunk-descriptions to find the best fit of chunks?"* — the user re-asserting descriptions two days before this file was rewritten. State: `grep -n "W_DESC\|chunk_desc_emb" v3/pipelines/artefact_v1.py` → `:125` `DESC_INDEX = "chunk_desc_emb"`, `:200` `W_DESC = _env_float("HERB_W_DESC", 1.0)` (verified) | **[CONTRADICTS-USER]** as written (1.15), ranked #3 | unreviewed |
| W-C48 | "Tags are per-chunk contextual phrases." | intent | `CQ "small concept.*node\|collective tags from a chunk"` — audit cites 06-11 (blackout, `[DOC]`) | **[GROUNDED]** (1.16) | unreviewed |
| W-C49 | "`herb-eval` (Neo4j) is the prior artefact build under the superseded design — a contrast/forensic baseline only, **not adopted**." | intent + state | Intent: `CQ "the v1artefact is using the same fucking neo4j db"` → L587, 2026-07-26T17:54. State: `grep -n "NEO4J_DATABASE" v3/pipelines/artefact_v1.py` → `:117` `DATABASE = os.environ.get("NEO4J_DATABASE", "herb-eval")` (verified) — every artefact number ever reported comes from it. Canon drift: `git show 0efff16:CLAUDE.md \| grep -n "herb-eval"` | **[STALE]** / live contradiction (1.17), ranked #7 | unreviewed |
| W-C50 | "never query `herb` (oracle-contaminated)" | intent | `CQ "DONT INCLUDE THE FUCKING EVAL FILES"` — audit cites 06-14 (blackout, `[DOC]`); also `CQ "dont fucking include the eval part"` | **[GROUNDED]** (1.17, second half) | unreviewed |

---

## Tier 2 — the 24 live laptop memory files (70 claims)

`C:\Users\jocke\.claude\projects\c--Coding-exjobbet-GRAG-Job\memory\`. These auto-load into every
Claude Code session on this machine — the same reach as `CLAUDE.md`, with none of the scrutiny.
The audit adjudicated 18 claims here, all from the behavioural entries; it barely touched the
`project_*` files, which is where the numbers live.

Run numbers, machine facts and audit findings are held in the repo rather than in memory:
`v3/output/DATA_README.md`, `docs/ENVIRONMENT.md`, `v3/CONSTANTS.md`,
`docs/canon/CONTRADICTION_MAP.md`. Rows whose claim moved there name the repo file as their
surface and are checked against it. Rows whose claim is asserted nowhere any more carry
`resolved — claim gone`; that status records that the sentence no longer exists, and is not a
ruling on whether it was true. The frozen copies under `docs/canon/raw/laptop_memory/` are
evidence of what memory once said and are never edited.

### 2a — `MEMORY.md` (the index — the part actually skimmed)

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-M01 | "Every entry below is an agent's claim about this project, and this index auto-loads into every session — neither fact makes an entry true or user-approved." | intent | `CQ "just because the text is in the repo"` → 08-02 | — | unreviewed |
| W-M02 | "`docs/canon/CANON_AUDIT.md` checked 18 claims from this memory surface: 12 grounded in a user quote, 1 agent-origin, 2 contradicting the record, 3 stale" | state | Count rows 4.1–4.18 in `CANON_AUDIT.md:359-380` and re-tally the verdict column by hand | — | unreviewed |
| W-M03 | Index line: "Ground answers in current repo docs — never analyze from stale/legacy/quarantined files **or git archaeology**" | intent | `CQ "GIT REPO HAS ALL THE FUCKING HISTORY"` → 08-02T22:42, and `CQ "you have to dig in the repo if you want true info"` → 08-02T21:23. The index line drops the body file's own "Git is fine as a tool" qualifier | **[CONTRADICTS-USER]** as summarised (4.3), ranked #4 | unreviewed |
| W-M04 | Index line: "**Run results live in the repo, not here** — `v3/output/DATA_README.md`: every run, every number, recomputed from disk. Haiku is the settled judge. No memory entry carries a run number." | state | `grep -rn "0\.6\\|0\.7\\|recall" MEMORY.md` over the live memory dir — the index must carry no run number for this line to be true. The gold-100 numbers it replaced are now in `v3/output/DATA_README.md` §gold-100 | **[STALE]** / **[CONTRADICTS-USER]** on the headline it replaced (4.6), ranked #10 | unreviewed |
| W-M05 | Index line: "**Audit findings live in the repo** — statistical claims that fail their own test and the benchmark landmines are in `v3/output/DATA_README.md`; the oracle-residue exposure is T3 in `docs/canon/CONTRADICTION_MAP.md`." | state | Open both named sections and confirm they hold the claims: `v3/output/DATA_README.md` §"Claims the statistics do not carry" and `CONTRADICTION_MAP.md` T3. The held-out headline this line replaced is now `DATA_README.md` §held-out-100, read under the unmatched-unit rule | **[STALE]** on the headline it replaced (4.7) | unreviewed |
| W-M06 | Index line: "metric validity table is binding (precision_id and nonllm are NOT cross-arm), truncate_k invalid for artefact context_ids" | state + intent | State: `grep -n "context_ids" v3/pipelines/artefact_v1.py` — are ids 1:1 with contexts? State: `v3/output/DATA_README.md`. Intent: `CQ "DATA_README\|binding"` — who declared it binding? | **[AGENT-ORIGIN]** on "binding" (3.5) | unreviewed |

### 2b — The behavioural entries (`feedback_*`)

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-M07 | `feedback_trust_revoked.md` | "Take **NO action** — no edits, no commits, no installs, no process starts/stops, no \"while I'm at it\" fixes — without an explicit instruction naming that action." | intent | Origin: `CQ "trust revoked"` → 07-16. Then the counter-evidence, which decides whether the absolutist form still stands: `CQ "just fucking DO shit\|build it ffs\|start working without a single fucking word"` | **[GROUNDED]** at origin, **[STALE]** in its absolutist form (4.5) | unreviewed |
| W-M08 | `feedback_trust_revoked.md` | "Questions get answers. Opinions get an honest read. Neither gets a tool call beyond read-only lookups." | intent | `CQ "Me having a fucking opinion will NEVER"` → 07-16 | **[GROUNDED]** at origin (4.5) | unreviewed |
| W-M09 | `feedback_trust_revoked.md` | "One thing at a time: propose the single next step, then stop and wait." | intent | `CQ "one thing at a time\|multi-step command"` | — | unreviewed |
| W-M10 | `feedback_visible_progress.md` | "First print within ~1s of launch … Long waits need heartbeats … **Never run user-facing work as an agent background task**" | intent | `CQ "fucing progress"` → 07-16T08:42; `CQ "perhaps thats a thing you should have in the .md"` → 07-16T08:53 | **[GROUNDED]** (4.8) | unreviewed |
| W-M11 | `feedback_background_workers.md` | "Dispatch every agent/worker in the background (`run_in_background: true`) … **Never** run an agent in the foreground" | intent | `CQ "highjacking my conversation"`. **Then reconcile with W-M10**, which says never background: the distinction (agents background, *runs* foreground in the user's terminal) is stated in neither file | **[GROUNDED]** (4.9), with the tension noted | unreviewed |
| W-M12 | `feedback_background_workers.md` | "This happened repeatedly on **2026-07-30** and made the user furious." | state | `CQ "highjacking my conversation"` returns 2026-07-29T22:48 — check whether the 07-30 date is right, and whether the file's own `modified: 2026-07-29T22:49` metadata contradicts its body | — | unreviewed |
| W-M13 | `feedback_commit_means_push.md` | "**any time the user asks me to commit, commit AND push in the same pass** — to a feature branch (e.g. `re-V1-k50`), NEVER main/legacy." | intent | `CQ "if i EVER ask you to commit"` → 07-23T16:25 | **[GROUNDED]**, verbatim (4.13) | unreviewed |
| W-M14 | `feedback_commit_style.md` | "Do NOT include the `Co-Authored-By: Claude ...` trailer, the \"🤖 Generated with Claude Code\" footer, or verbose multi-paragraph AI-generated bodies." | intent | `CQ "co.author\|Co-Authored\|attribution\|footer\|generated with"` → **0 hits in 803 turns** (verified). The May/June blackouts could hold it and desktop `no-claude-attribution.md` suggests it is real → `cannot-determine`, not `unsupported`. Corroborate from state: `git log --format=%B -50 \| grep -c "Co-Authored"` | Rule **[AGENT-ORIGIN]** (4.4) | unreviewed |
| W-M15 | `feedback_commit_style.md` | "**Why:** This is the user's exjobb (master's thesis) project. They do not want AI attribution … it reflects on their academic work." | intent | `CQ "drop the fucking thesis\|post-thesis\|why the fuck are you going on about"` → 06-14, 07-22, 07-30 all say the thesis is done. The *rule* may survive; this *rationale* is the thing to rule on | Rationale **[CONTRADICTS-USER]** (4.4) | unreviewed |
| W-M16 | `feedback_final_audit_panel.md` | "Before any conclusions … are treated as final/shippable, run a final audit panel of three parallel adversaries: 1. A PhD+ academic-rigor examiner … 2. A senior-engineer … audit. 3. An overfitting/leakage/weak-baseline/unseen-data specialist." | intent | `CQ "adversar"` and `CQ "overfitting"` — the audit cites 07-23T14:07 as the user specifying all three roles in one sentence; the memory file says the gate was "established 2026-07-25". Settle the date | **[GROUNDED]**, verbatim (4.17) | unreviewed |
| W-M17 | `feedback_final_audit_panel.md` | "As of the 2026-07-25 state doc, it had NOT been run … Before treating any current numbers as conclusive, check whether this panel has since run" | state | The 07-28 audit's surviving output: `v3/output/DATA_README.md` §"Claims the statistics do not carry", `CONTRADICTION_MAP.md` T3, and the OneDrive state doc `2026-07-28-audit-absorption-full-revert-corroboration-probe.md`. Read them and rule whether they satisfy all three lenses (academic rigor / senior engineer / overfitting-leakage) or only some | — | unreviewed |
| W-M18 | `feedback_grounding.md` | "Do not reason from stale, legacy, or quarantined files; do not substitute git-log/diff archaeology for reading the actual docs." | intent | `CQ "you have to dig in the repo if you want true info"` → 08-02T21:23, said of a branch deliberately cleared of the design era | **[CONTRADICTS-USER]** as summarised (4.3) | unreviewed |
| W-M19 | `feedback_grounding.md` | "Git is fine as a tool; the earlier \"stop gitting\" was about using archaeology to *avoid* reading docs, not a ban on git." | intent | `CQ "stop gitting"` — does the phrase appear in the corpus at all? | — (the audit calls this the careful version the index drops) | unreviewed |
| W-M20 | `feedback_grounding.md` | "Terse, blunt, profane feedback from this user = real signal; stop, re-ground, don't get defensive." | intent | `CQ "reacting to getting yelled"` → 07-21T11:10 | — | unreviewed |
| W-M21 | `feedback_infer_context_like_a_human.md` | "their words (2026-07-16): \"I EXPECT you to infer context via human language… answering in the max-autistic way is the absolute opposite of that.\"" | intent | `CQ "infer context via human language"` — this is quoted *as* the user's words, so it must match the corpus exactly or the entry is misquoting him | **[GROUNDED]**, near-verbatim (4.12) | unreviewed |
| W-M22 | `feedback_judge_run_cost_math.md` | "three parallel `--rejudge` runs (haiku+sonnet+opus …) drained the user's entire Claude subscription window in ~30 s." | intent + state | `CQ "burned almost my entire usage in 30 seconds"` → 07-17 | **[GROUNDED]** (4.10, 3.7) | unreviewed |
| W-M23 | `feedback_judge_run_cost_math.md` | "Every judged cell ships the full k=50 contexts (~50–100k tokens) per judge call … The claude CLI bills the same 5-hour window the user's own Claude Code sessions use" | state | Read a real manifest: `python -c "import json;print(json.load(open('v3/output/<judged-dir>/eval_manifest.json')))"` and check recorded token usage against ~50–100k/call | — | unreviewed |
| W-M24 | `feedback_never_relaunch_expensive_runs.md` | "When a claude-* run (judge or generator) FAILS, STOP. Diagnose from the output already on disk. Do NOT relaunch … A retry is a fresh full-cost run — estimate tokens x calls out loud and get the user's explicit go BEFORE EACH attempt" | intent | `CQ "burned 70% usage\|burned my entire usage in 5 minutes\|waste all my usage"` → 07-23, 07-24 | **[GROUNDED]** (4.10) | unreviewed |
| W-M25 | `feedback_orchestrator_mode.md` | "Claude in the main conversation is **only the orchestrator and the one who talks to the user**. Every actual job the user asks for is delegated to an agent" | intent | `CQ "always only the orchestrator"` → L455, 07-22T15:36 | **[GROUNDED]**, verbatim (4.14) | unreviewed |
| W-M26 | `feedback_react_to_anger.md` | "When the user is angry: first say plainly what I got wrong and why it angered them, then fix it." | intent | `CQ "reacting to getting yelled and cursed at"` → 07-21T11:10 | **[GROUNDED]**, near-verbatim (4.11) | unreviewed |
| W-M27 | `feedback_react_to_anger.md` | "Data requests: the COMPLETE data goes in the message body on the first ask — tables rendered in markdown, never summarized down to two numbers, never left inside a tool result." | intent | `CQ "table\|tool result"` around 07-21 | — | unreviewed |
| W-M28 | `feedback_reusable_tools.md` | "New functionality = a general tool with folder/ids/model arguments that works on any run dir … Never weld a tool to one experiment's files" | intent | `CQ "custom scripts i cant reuse"` → 07-17T12:18 | **[GROUNDED]**, verbatim (4.15) | unreviewed |
| W-M29 | `feedback_user_concepts_are_canon.md` | "fuzzy clustering (soft, overlapping, query-relative membership), levels of k's …, independent areas per prompt need, progressive opening of areas under a hard k" are the user's own concepts; "gap cut", "NNK pruning", "RRF fusion", "spheres" are agent substitutions | intent | `CQ "fuzzy clustering\|levels of k"` → 07-20; `CQ "NONE of these are something i named or invented"` → 07-20 | **[GROUNDED]** — the audit calls this the best entry in the memory (4.2) | unreviewed |
| W-M30 | `feedback_user_concepts_are_canon.md` | "The state doc docs/state/2026-07-20-v1-query-relative-areas.md separates user canon from assistant interpretation — **follow its §3 facts and terminology rules**." | intent | A state doc is made binding on all future sessions. `CQ "state doc"` — did the user adopt it? Note 07-22: *"i am going to assume that the agent that wrote the state doc now was.. unhelpful"* (`CQ "agent that wrote the state doc"`) | — (same pattern the audit flags at 3.4) | unreviewed |
| W-M31 | `feedback_user_concepts_are_canon.md` | "This is the user's master's thesis; the concepts ARE the contribution." | intent | `CQ "drop the fucking thesis\|post-thesis"` — same rationale conflict as W-M15 | — | unreviewed |

### 2c — The design and vocabulary entries

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-M32 | `project_terminology_canon.md` | "**Current arm (user's design) terms:** … **pool** … **areas** … **anchors** … **levels** … **support** … **walk** … **stated-scope part**" | intent | Run each term separately and read every hit to see whether it is the user's own word or him echoing agent text: `CQ "\bwalk\b"`, `CQ "\banchor"`, `CQ "stated.scope"`, `CQ "\bsupport\b"`, `CQ "levels of k"`, `CQ "areas"`, `CQ "\bparts\b"` | **[CONTRADICTS-USER]** (4.1), **ranked #1** — the audit says five of seven are absent except as agent text | unreviewed |
| W-M33 | `project_terminology_canon.md` | Provenance line: "Grounded 2026-07-21 from v3/README.md, v3/output/DATA_README.md, docs/state/2026-07-20-v1-query-relative-areas.md §3-4, CLAUDE.md, and the live code." | state | Read the line at `project_terminology_canon.md:10-11`. Every named source is an agent artifact; none is the corpus. That is checkable by inspection and decides how much W-M32 can be worth | — | unreviewed |
| W-M34 | `project_terminology_canon.md` | "**artefact** (British spelling) = the system under test … **artifact** (HERB's spelling) = one source record in the corpus carrying an `id`. Never mix." | intent + state | `CQ "artefact\|artifact"` for the user's own usage; `grep -rn "artifact" v3/README.md` → the README's own arm is spelled `artifact`, which this rule forbids | **[CONTRADICTS-USER]** noted at 2.1 (the reference file breaks its own canon) | unreviewed |
| W-M35 | `project_terminology_canon.md` | "`context_precision_id`: NOT cross-arm comparable (denominator = every id carried by retrieved chunks; id-density differs per arm ~500 vs ~50)." | state | Compute id counts per arm from `v3/output/*/arm_outputs.jsonl`: `python -c` mean `len(context_ids)` per arm. The ~500 vs ~50 ratio is the whole argument | — | unreviewed |
| W-M36 | `project_terminology_canon.md` | "truncate_k slicing `context_ids[:k]` is therefore invalid for the artefact arm (discovered 2026-07-21)" | state | `grep -n "context_ids" v3/truncate_k.py v3/pipelines/artefact_v1.py` — prove non-1:1 alignment from the code, not from the claim | — | unreviewed |
| W-M37 | `project_terminology_canon.md` | "**Facets** = topic/entities/activity/temporal/evidence." | state | `grep -rn "topic\|entities\|activity\|temporal\|evidence" v3/pipelines/artefact_v1.py \| head` and `grep -n "facet" v3/artefact/tag.py`. Then reconcile with the three incompatible "settled" facet sets the audit found in desktop memory (W-E24) | — | unreviewed |
| W-M38 | `project_terminology_canon.md` | "\"surface\" (desc/structural) is an AGENT coinage in code/docstrings, not user-named — flag for renaming." | intent | `CQ "surface"` and `CQ "\bdoor\b"` → 07-29: *"Dude, what is with that fucking herb door trace!? WHAT DOES IT EVEN MEAN!?"*. This entry flags one coinage while W-M32 launders four | — (the audit's ranked #1 turns on exactly this asymmetry) | unreviewed |
| W-M39 | `project_agent_roster.md` | "Since 2026-07-22 the repo has a permanent specialist agent roster in `.claude/agents/` (ten definitions, **adversarially verified at creation**)." | state | `ls .claude/agents/*.md \| wc -l` → 10; `git log --oneline --diff-filter=A -- .claude/agents/` for the creation commit. "Adversarially verified" needs an artifact — find it or rule `cannot-determine` | **[GROUNDED]** on the roster itself (3.13) | unreviewed |
| W-M40 | `project_agent_roster.md` | "Definitions are docs — when canon changes, update the affected agent definitions in the same pass." | intent | `CQ "agent"` around 07-22 — is this maintenance rule the user's or the agent's? | — | unreviewed |
| W-M41 | — | "The real, current line of work is the branch **`origin/djuret/monorepo`** … `main` lineage is a divergent, stripped/mock state" | state + intent | No surface asserts this. `origin/djuret/monorepo` still exists at `fb311f6` and is the frozen pre-v3 line; `CLAUDE.md` §"Repo layout" and `CONTRADICTION_MAP.md` §"Layer scoping" put the work in `v3/`. The quarantine half survives as `CLAUDE.md`'s hard rules — `CQ "quarantine"` → 05-14 | **[GROUNDED]** (4.16) | resolved — claim gone |
| W-M42 | `v3/CONSTANTS.md` · `ALL_FACETS` | "`("topic", "entities", "activity", "temporal", "evidence")` … **borrowed** — the facet set baked into `herb-eval`'s `HAS_TAG.facets`; the arm must match the graph it queries" | state | `grep -n "ALL_FACETS" v3/pipelines/artefact_v1.py` and Cypher `MATCH ()-[r:HAS_TAG]->() RETURN r.facets LIMIT 1`. `CONTRADICTION_MAP.md` T9 records that three different "settled" sets are asserted across the repo and that only this one is in force; D13 says why | — | unreviewed |
| W-M43 | `docs/ENVIRONMENT.md` §State-transfer docs | "They sit **flat** under the OneDrive additional working directory … not nested under `docs/state/` / `docs/handoff/` the way prose paths name them" | state | `ls "C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/"*.md` — paste the listing | **[STALE]** on CLAUDE.md's side (7.7) | unreviewed |
| W-M44 | — | "CLAUDE.md's line 1 still names `2026-07-22-v1-curve-walk-facets-and-cluster-k.md` as the current entry point" | state | `grep -n "2026-07" CLAUDE.md` → CLAUDE.md names no state doc as its entry point; its §"Session entry point" names `docs/canon/raw/user_turns_all.md`. Nothing asserts this claim | — | resolved — claim gone |

### 2d — The environment entries

Machine facts are held in `docs/ENVIRONMENT.md`, committed and per-machine, so these rows check a
repo file rather than a memory entry.

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-M45 | `docs/ENVIRONMENT.md` §graphify | "`graphify` 0.8.39 is installed (miniconda Scripts); `python refresh_graph.py` runs on this machine." | state | `python -c "import graphify; print(graphify.__version__)"` | — | unreviewed |
| W-M46 | `docs/ENVIRONMENT.md` §Neo4j | "`herb-eval` is loaded from the repo's git-lfs dump (`v3/artefact/data/herb-eval.dump`): **4,869 chunks, 19,716 tags, 67,913 HAS_TAG edges**, `tag_emb` + `chunk_desc_emb` + `chunk_fulltext` indexes, **zero oracle chunks**, single run_id `pilot_full_herb`." | state | Needs Neo4j up (start recipe is in the same file). Cypher: `MATCH (c:Chunk) RETURN count(c)`, `MATCH ()-[r:HAS_TAG]->() RETURN count(r)`, `SHOW INDEXES`. "Zero oracle chunks" is the load-bearing one — it is the quarantine claim, and `CONTRADICTION_MAP.md` T3 holds the wider residue question it does not settle | — | unreviewed |
| W-M47 | `docs/ENVIRONMENT.md` §Neo4j | "auth DISABLED **at the user's direction** (localhost-only dev DB)" | intent | `CQ "neo4j\|auth\|password"` — attribution to the user needs a quote | — | unreviewed |
| W-M48 | `docs/ENVIRONMENT.md` §Python | "**Never wipe an env directory without freezing its metadata first** — site-packages metadata is the only record of the versions a past run used." Same section: "`v3/requirements.txt` here is a laptop reconstruction (ragas 0.4.3)" and the desktop `.venv` is "the authoritative version record" | state + intent | `CQ "venv"` → the user's own account of the 2026-07-16 incident the rule comes from; `git log --oneline -- v3/requirements.txt`; `pip show ragas` on this machine against the desktop freeze | **[GROUNDED]** in spirit via 4.5's incident list | unreviewed |
| W-M49 | `docs/ENVIRONMENT.md` §Headless Claude CLI | "Aliases: `haiku` → claude-haiku-4-5-20251001 (200k ctx / 32k out) · `sonnet` → claude-sonnet-5 · `opus` → claude-opus-4-8 · `fable` → claude-fable-5" | state | The resolved ids appear in `v3/output/*/eval_manifest.json`. **Do not spend a model call to re-verify** — read the manifests | — | unreviewed |
| W-M50 | `docs/ENVIRONMENT.md` §Headless Claude CLI | "`--json-schema '<schema>'` enforces a JSON Schema on the response, so the generator's `{\"answer\": str}` contract and the judge verdict can both be schema-enforced. No temperature flag exists; reproducibility is this path's one real gap versus NIM." | state | `C:/Users/jocke/.local/bin/claude.exe --help \| grep -n "json-schema"` and `grep -n "json-schema\|fence" v3/eval/ragas.py` — the code still fence-strips, so check whether the schema path is used or only available | — | unreviewed |

### 2e — The results entries (where the numbers live)

The audit adjudicated two of these on framing (4.6, 4.7) and left the rest untouched. Every row
here is a number that can be recomputed from `v3/output/` — none needs a model call.

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-M51 | `project_benchmark_validity_caveats.md` | "**Cross-arm VALID:** context_recall_id (exact, gold-set denominator), and the judged trio under one judge" | state | Recompute recall_id per arm from `v3/output/*/eval_results.jsonl`; read each `eval_manifest.json` to confirm one judge | — | unreviewed |
| W-M52 | `project_benchmark_validity_caveats.md` | "`gold100.jsonl` is 22 person / 55 content / 17 pr / 5 company / 1 url — NOT the equal 20-per-type draw `build_question_sets.py` produces" | state | **[user-gated]** — the direct check opens `gold100.jsonl`. Indirect route: per-type counts from any gold-100 run's `eval_results.jsonl` (`type` is re-joined at eval time). Propose, do not open | — | unreviewed |
| W-M53 | `project_benchmark_validity_caveats.md` | "**Company questions are two-hop joins** … lucene+vector ingest `products/` ONLY … so they structurally cannot answer them" | state | `grep -n "products\|metadata" v3/pipelines/lucene.py v3/pipelines/vector.py`; `git log --oneline a45292f -1` for the "baked in since the arms' first commit" claim | — | unreviewed |
| W-M54 | `project_benchmark_validity_caveats.md` | "**Artefact system bottleneck is extraction, not retrieval:** its contexts hold 87% of gold employee-ids; its answers surface 26%." | state | Recompute from a gold-100 artefact run's `arm_outputs.jsonl` (contexts + answers) against gold ids. Note the gold side is **[user-gated]** if it needs `questions.jsonl` — route via `eval_results.jsonl` | — | unreviewed |
| W-M55 | `project_benchmark_validity_caveats.md` | "**Baselines abstain a lot:** \"not in the documents\" — lucene 38/100, vector 35/100, artefact 6/100." | state | Count the abstention string in each arm's `arm_outputs.jsonl` | — | unreviewed |
| W-M56 | — | "**Headline (cross-arm valid):** artefact_v1 leads every valid metric. context_recall_id 0.636 vs lucene 0.089 / vector 0.113 (7× / 5.6×)" | state | No surface asserts this. `v3/output/DATA_README.md` §"Claims the statistics do not carry" states the opposite — "'Leads all valid metrics' is false as worded" — and its k=50 table carries the numbers under the unmatched-unit rule that disqualifies the ratio. `CANON_AUDIT.md` 4.6 keeps the deleted wording as its finding | **[STALE]** / **[CONTRADICTS-USER]** in framing (4.6) | resolved — claim gone |
| W-M57 | `v3/CONSTANTS.md` · `JUDGE_MODEL` | "**user-specified** — 'try haiku first then, and we can do this headless in the same way?' (turns:L1186); 'we decided to use haiku for the fucking evals also' (turns:L3820)" | intent | `CQ "haiku"` → confirm both quotes land at those lines and that neither is a question rather than a decision. `v3/README.md` §Decided asserts the same default | **[GROUNDED]** (3.6, 2.4) | unreviewed |
| W-M58 | `v3/output/DATA_README.md` §Known properties | "**Generator confound (judged/answer metrics only):** in Trio A the artefact answers come from `claude-sonnet-5` and both baseline answers from `qwen3.5-397b`. Retrieval id metrics are unaffected" | state | Read `generator` from each Trio A run's `run_manifest.json` and paste them side by side | — | unreviewed |
| W-M59 | `v3/output/DATA_README.md` §"Runs that are not here" | "**No `artefact_v1_det` held-out run.** The one attempt reached 1 of 100 and its `failures.jsonl` is empty, so the cause is unknown. Every held-out number in this file comes from the interpreting leg." | state | `ls v3/output/ \| grep heldout` — the dead folder is not retained, so this is checkable only as an absence plus the surviving held-out runs' manifests | — | unreviewed |
| W-M60 | `project_adversarial_panel_verdicts.md` | "**The curve-walk stop rule must not ship as the K-decider.** … permutation test: shuffling each chain's gaps gives 60.1±4.1 stops vs 67 real — the statistic carries almost no order information" | state | The panel's scratchpad is gone; check whether the permutation can be re-run from `v3/output/*TRACE*` dirs. If not reproducible from disk → `cannot-determine` | **[GROUNDED]** (4.18) | unreviewed |
| W-M61 | `project_adversarial_panel_verdicts.md` | "**Canon conflicts requiring USER decisions** (not agent calls): (a) \"model emits no numbers, ever\" vs pass-2 interpreter emitting 0.0-1.0 facet scores; (b) \"no answer-sufficiency oracle\" canon vs the sufficiency review; (c) \"the chunk description is dead\" vs an arm that hard-requires desc_emb" | state | All three are verifiable in code today: `v3/pipelines/artefact_v1.py:645`, `:774`, `:125`, `:200` (verified). These are W-C46 and W-C47 restated — and they have been open since 07-22 | — | unreviewed |
| W-M62 | `v3/output/DATA_README.md` §"The unmatched-unit rule" + §"gold-100 at a matched retrieval budget" | "**A cross-arm ratio read at a common k is not a like-for-like lead and must never be presented as one**"; "At a matched id budget the artefact-det lead over the strongest baseline is **0.7339 vs 0.4100, a ratio of 1.79×**" | state | Re-run the id-budget matching over `v3/output/*gold100*/arm_outputs.jsonl` against the k=500 hybrid-arm runs. Two notes: the deleted entry's one-id-per-chunk counterfactual (artefact → 0.0904) is recorded on no live surface, so decide whether it should be; and which of gap / ratio ships is `CONTRADICTION_MAP.md` T10, the user's call | — | unreviewed |
| W-M63 | `docs/canon/CONTRADICTION_MAP.md` D14 | "`WALK_GATE` was built and is live (`artefact_v1.py:148-152` …); `SCOPE_REACH` and `TAG_PURE` appear nowhere under `v3/**/*.py`" | state | `git log -S"HERB_SCOPE_REACH" --oneline --all` and `grep -rn "HERB_SCOPE_REACH\|HERB_TAG_PURE" v3/`. `project_v1_machinery_fix_and_toggles.md` (W-M66) and `v3/output/DATA_README.md` §"scope-reach / tag-pure grid" both describe the same three names — check all three read the same way | — | unreviewed |
| W-M64 | `project_corroboration_probe_verdict.md` | "**Oracle headroom quantified: +0.2125 recall from a 10-slot in-territory swap** (0.7339→0.9463) … Part-J step-(3) discriminator remains unfound." | state | Scripts live in a 2026-07-29 session scratchpad, not the repo. If nothing on disk reproduces it → `cannot-determine`. Same evidence gap as W-C13 | — | unreviewed |
| W-M65 | `v3/output/DATA_README.md` §"gold-100 at a matched retrieval budget" | "`hybk500…` hybrid, k=500 … 0.3883 … paired delta vs det **+0.3455**, 95% CI [+0.3024, +0.3887], W/L/T 93/5/2" | state | Recompute from `hybk500__gold100__20260723T154340Z` and `artefact_v1_det__gold100__20260801T072455Z`. The deleted entry claimed ~0.27 against the hybrid and that the lead is "NOT an id-budget artifact"; the surviving record states the delta and leaves which framing ships to T10 | — | unreviewed |
| W-M66 | `project_v1_machinery_fix_and_toggles.md` | "Three experiment flags (all off = byte-identical, proven bitwise/byte-level …): HERB_SCOPE_REACH=1 …, HERB_TAG_PURE=1 …, HERB_WALK_GATE=1" | state | `grep -rn "HERB_SCOPE_REACH\|HERB_TAG_PURE\|HERB_WALK_GATE" v3/` → contradicted by W-M63 | — | unreviewed |
| W-M67 | `project_v1_ordering_diagnosis.md` | "**How to apply:** any ranking-change proposal must beat scope-alone (**0.7926 det 10smoke**) before it's interesting" | state + intent | This is the origin of the bar the audit condemns in `maths-algorithmist.md` (W-A18). State: recompute 0.7926 from `v3/output/artefact_v1_detTRACE__10smoke__20260722T050703Z`. Intent: `CQ "pass.?fail"` → 07-31T23:09, and `CQ "we already have the fucking scores to compare to"` | **[CONTRADICTS-USER]** where it is enforced as a gate (3.2), ranked #5 | unreviewed |
| W-M68 | `project_v1_ordering_diagnosis.md` | "**Pool ceiling recall = 1.000 on every question, both legs.** Membership is solved; the whole gap … is ordering inside the pool." | state | The 07-28 audit calls this "unverifiable from disk (traces carry locators, not ids) — cite as n=10 diagnostic only". Check the trace dirs and see which is right | — | unreviewed |
| W-M69 | `project_curve_cut_experiment.md` | "**User verdict:** the walk and the straight-fit break rule are NOT helping each other." | intent | `CQ "walk and the .best fit"` → 07-22: *"i dont think the walk and the 'best fit' is helping eachother, you?"* — that is a **question**, not a verdict. Attribution of an agent measurement to a user ruling is the audit's core pattern | **[CONTRADICTS-USER]** in attribution (3.14, 7.5) | unreviewed |
| W-M70 | `project_v1_lineage_and_cost_delta.md` | "The specific cost multipliers (240k chars median, ~18×, ~26s/q, etc.) are relayed from a separate analysis session and were **NOT found verbatim** in the state doc — still not independently re-derived from raw run logs." | state | This entry marks its own numbers unverified — the honest handling. Re-derive from `v3/output/*/arm_outputs.jsonl` char counts, or leave as the entry states it | — | unreviewed |

---

## Tier 3 — the 10 agent definitions (50 claims)

`.claude/agents/*.md`. A line here becomes a hard rule the instant an agent spawns, and the agent
has no way to question it — it arrives as the agent's own instructions. The audit adjudicated 14
claims here and called this surface's grounded-to-invented ratio the worst in the repo (6 vs 6).

**Line-number warning, verified.** Every line citation in `CANON_AUDIT.md` for this surface is
off by 9. The audit cites `logician.md:41`, `code-optimizer.md:35`, `critical-reviewer.md:38`,
`eval-statistician.md:44`, `maths-algorithmist.md:34`, `graph-refresher.md:23`; the current
lines are 50, 44, 47, 53, 43 and 32. A 9-line "Interpretation, not intent" banner was prepended
to all ten files on 2026-08-03, after the audit read them. Re-locate before quoting — and treat
this as a live demonstration of why a verdict must paste the output of a command run *now*.

### 3a — Present in all ten definitions

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-A01 | The banner, identical in all ten: "`docs/canon/CANON_AUDIT.md` checked 14 claims made by the agent definitions: 6 grounded in a user quote, 6 agent-origin, 2 contradicting the record" | state | `grep -c "checked 14 claims" .claude/agents/*.md` (expect 1 per file); then count rows 3.1–3.14 in `CANON_AUDIT.md:332-349` and re-tally. An unreviewed audit's counts are now asserted on ten enforced surfaces | — | unreviewed |
| W-A02 | The banner: "This definition is an agent's claim about how to work here, not the user's approval of it." | intent | `CQ "just because the text is in the repo"` → 08-02 | — | unreviewed |

### 3b — The terminology rule (six definitions)

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-A03 | `logician.md:50` | "**areas / levels / walk / anchor / support / stated-scope / parts** are the user's concepts — never rename or substitute them, never introduce coinages of your own." | intent | Per-term corpus runs, reading every hit for whether it is the user's word or his echo of agent text: `CQ "\bwalk\b"`, `CQ "\banchor"`, `CQ "stated.scope"`, `CQ "\bsupport\b"`, `CQ "areas"`, `CQ "levels of k"`, `CQ "\bparts\b"` | **[CONTRADICTS-USER]** (3.1), **ranked #1** | unreviewed |
| W-A04 | `code-optimizer.md:44` | "**areas / levels / walk / anchor / stated-scope / support** are the user's concepts. Never rename or substitute them in code, comments, or reports." | intent | Same as W-A03 | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A05 | `critical-reviewer.md:47` | "Areas, levels, walk, anchor, support, stated-scope, parts are the user's concepts — use them exactly, never rename or substitute, and flag code that does as a finding." | intent | Same as W-A03. Note this one makes the unverified list *enforceable against other agents' code* | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A06 | `eval-statistician.md:53` | "Areas, levels, walk, anchor, support, stated-scope, parts are the user's concepts — use them verbatim, never rename or substitute" | intent | Same as W-A03 | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A07 | `maths-algorithmist.md:43` | "parts, pool, anchor, levels, support, areas, walk, stated-scope are the USER's concepts — never rename or substitute them; \"doors\"/\"surfaces\" are agent coinages, flag them as such when used." | intent | Same as W-A03, plus: `CQ "\bdoor\b"` → 07-29 *"what is with that fucking herb door trace!? WHAT DOES IT EVEN MEAN!?"*. This file protects four unverified coinages in one clause while correctly naming two others in the next | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A08 | `graph-refresher.md:32` | "parts / areas / levels / anchor / walk / support / stated-scope are the user's concepts, never renamed or substituted" — applied to every graph label written | intent | Same as W-A03. Consequence is durable: these labels feed the navigation graph every future session reads | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A09 | `order-of-operations.md:51` | "**parts / areas / levels / anchor / walk / support / stated-scope** are the user's concepts — never rename or substitute them." | intent | Same as W-A03 | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A10 | `results-analyst.md:58` | "**parts / areas / levels / anchor / walk / support / stated-scope** are the user's concepts — never rename them, never substitute agent coinages." | intent | Same as W-A03 | **[CONTRADICTS-USER]** (3.1) | unreviewed |
| W-A11 | `retrieval-scientist.md:56` | "Query-relative areas, levels of k's, cluster-K, walk, anchor, stated-scope, parts, support, gate are the USER's concepts … **Gap cut, NNK, RRF, spheres, knee, surface, door are agent coinages** — unaccepted translations" | intent | Same as W-A03. This is the only definition that puts "door" on the *coinage* side, where the audit says it belongs — check whether the two halves of its own list survive the same test | — (the audit's ranked #1 turns on this inconsistency) | unreviewed |
| W-A12 | `v3-coder.md:34` | "Restate the change to yourself in the user's terms (parts, areas, levels, anchor, walk, support, stated-scope — never a substitute term)." | intent | Same as W-A03 | **[CONTRADICTS-USER]** (3.1) | unreviewed |

### 3c — The metric-validity table declared binding (five definitions)

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-A13 | `critical-reviewer.md:20` | "cross-arm claims built on invalid metrics (`context_precision_id` and `nonllm`/text metrics are NOT cross-arm comparable — **the validity table in `v3/output/DATA_README.md` is binding**)" | intent + state | Intent: `CQ "DATA_README"` — no user ruling adopts it. State: the table's *content* is checkable (W-M35) | **[AGENT-ORIGIN]** (3.5) | unreviewed |
| W-A14 | `eval-statistician.md:32` | "`v3/output/DATA_README.md` — the binding metric-validity table for the shipment data." | intent | Same as W-A13 | **[AGENT-ORIGIN]** (3.5) | unreviewed |
| W-A15 | `logician.md:51` | "The metric-validity table is **binding logic** … Flag any reasoning that assumes otherwise as a FAILS." | intent | Same as W-A13. Here an agent-written table becomes a logical axiom that other agents' reasoning is failed against | **[AGENT-ORIGIN]** (3.5) | unreviewed |
| W-A16 | `maths-algorithmist.md:44` | "**Metric validity is binding:** `context_recall_id` is the cross-arm metric; `context_precision_id` and nonllm/text metrics are NOT cross-arm comparable" | intent | Same as W-A13 | **[AGENT-ORIGIN]** (3.5) | unreviewed |
| W-A17 | `results-analyst.md:30` | "`v3/output/DATA_README.md` — shipment notes and the metric validity table. **That table is BINDING.**" | intent | Same as W-A13 | **[AGENT-ORIGIN]** (3.5) | unreviewed |

### 3d — Pre-registered bars and closed findings

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-A18 | `maths-algorithmist.md:38` | "**Compare against the standing bars before proposing.** A ranking change is only interesting past scope-alone (0.7926 det 10smoke); a per-query-K mechanism is only interesting past a constant cut at the same mean depth." | intent | `CQ "pass.?fail"` → L732, 2026-07-31T23:09 *"what the fuck are you even talking about, pass fail?"* (verified); then `CQ "we already have the fucking scores to compare to"` → 07-31T23:10. Three consecutive turns rejecting a bar of exactly this shape | **[CONTRADICTS-USER]** (3.2), **ranked #5** | unreviewed |
| W-A19 | `maths-algorithmist.md:24` | "**Never re-derive or re-propose what these close:** value-knee ≡ constant cut; the option-2 walk is ceiling-bound; … every re-rank of existing door values walls at ~0.79–0.80; stored w_facets are non-signal." | state + intent | The 07-28 audit found several of these not statistically significant (W-M62, and "clusterKglob best config: NOT supported, p=0.36"). Forbidding re-derivation of a null result makes it a law. Check each sub-claim's significance from disk | **[AGENT-ORIGIN]**, partly invalidated (3.3) | unreviewed |
| W-A20 | `maths-algorithmist.md:25` | "`docs/state/2026-07-22-v1-curve-walk-facets-and-cluster-k.md` — current design state, the user's verdicts, rejected interpretations (**§8 is binding**)." | intent + state | State: `ls docs/state/` → the folder does not hold it (W-C12); the file is in OneDrive. Intent: `CQ "agent that wrote the state doc"` → 07-22, the user pre-emptively distrusting this exact document | **[AGENT-ORIGIN]** (3.4, 7.3) | unreviewed |
| W-A21 | `maths-algorithmist.md:40` | "Mechanisms **the user judged not working** (the chord break gluing, the value-knee) stay dead unless the user reopens them." | intent | `CQ "walk and the .best fit"` → 07-22, a question not a ruling; `CQ "value.knee\|knee"`. The verdicts were agent measurements | **[AGENT-ORIGIN]** — attribution is false (3.14) | unreviewed |
| W-A22 | `retrieval-scientist.md:49` | "a per-question mechanism must beat the constant cut at the same mean depth on the same ordering (**the pre-registered bar** …); an artefact ordering change must beat scope-alone on the same leg and set." | intent | Same as W-A18 — the rejected bar, second instance | — (same class as 3.2) | unreviewed |
| W-A23 | `retrieval-scientist.md:20` | "re-proposing a mechanism already measured and rejected (the project has a **graveyard**: value-knee cuts, chord walks, spacing-based stop rules, re-ranks of existing door values)" | state | Same as W-A19 | — | unreviewed |
| W-A24 | `eval-statistician.md:24` | "the settled daily judge is claude-haiku-4-5 (**a closed decision — do not reopen it**)" | intent | `CQ "we decided to use haiku"` → 07-29 | **[GROUNDED]** (3.6) | unreviewed |

### 3e — Design claims propagated into enforced rules

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-A25 | `retrieval-scientist.md:15,25` | "artefact (graph retrieval, the system under test, **built natively in v3/artefact/** …)" and "Artefact design you hold exactly: the closed graph spine Source → File → Chunk → Tag — the only nodes … **The model emits no numbers, ever** (tagger and interpreter)." | intent + state | Intent: `CQ "NOT doing the v3 artefact"` → L588. State: `v3/pipelines/artefact_v1.py:645` and `:774` — the shipping interpreter emits and validates facet numbers (verified). An agent told to "hold exactly" this cannot read the arm it works on | **[CONTRADICTS-USER]** (1.10/2.1), **[STALE]** as applied (1.14) | unreviewed |
| W-A26 | `retrieval-scientist.md:25` | "Facets are weight+direction carried on the tag edge (one edge per tag with the full facet vector)." | state | `grep -n "w_facets\|facets" v3/pipelines/artefact_v1.py \| head`; and the built tagger emits no facets at all (`v3/artefact/tag.py:4`, verified) | — | unreviewed |
| W-A27 | `retrieval-scientist.md:25` | "Design canon lives in the state doc CLAUDE.md's session entry point names — **DESIGN.md and MODEL_CONTRACTS.md are stale; never re-derive from them.**" | state | `ls docs/state/` (empty on this machine) — the named canon is unreachable while the forbidden files are present. Same as W-C14 | — | unreviewed |
| W-A28 | `retrieval-scientist.md:61` | "**Three canon conflicts stand open for the USER** (project_adversarial_panel_verdicts.md item 5): flag them when touched, never resolve them yourself." | state | The three are W-M61 / W-C46 / W-C47, verifiable in code today, open since 2026-07-22 | — | unreviewed |
| W-A29 | `v3-coder.md:51` | "Never query the `herb` Neo4j database (oracle-contaminated); `herb-eval` is forensic contrast only." | intent + state | State: `v3/pipelines/artefact_v1.py:117` defaults to `herb-eval` (verified) — the arm this agent maintains queries the database this rule calls forensic-only. Intent: `CQ "the v1artefact is using the same fucking neo4j db"` → L587 | **[STALE]** / live contradiction (1.17) | unreviewed |
| W-A30 | `v3-coder.md:29` | "Filenames lie here (docs say `pipelines/artifact.py`; the file on disk is `pipelines/artefact.py`)." | state | `ls v3/pipelines/` → confirmed true (verified). A correct claim; the row exists because the doc it corrects (`CLAUDE.md`, W-C43) is still wrong | — | unreviewed |
| W-A31 | `order-of-operations.md:20` | "`context_ids` are deduped **in rank order** and are NOT aligned 1:1 with `contexts`, so slicing `context_ids[:k]` silently corrupts artefact-arm truncation" | state | `grep -n "context_ids" v3/pipelines/artefact_v1.py v3/truncate_k.py` — prove it from the code | — | unreviewed |
| W-A32 | `critical-reviewer.md:20` | "corruption of the shared-generator contract (**the system instruction must stay byte-identical across arms**)" | state | `grep -rn "Answer the question using only the provided documents" v3/` — is it one shared constant or duplicated per arm? | **[GROUNDED]** as a principle (2.9) | unreviewed |

### 3f — Method and behaviour rules

| id | surface | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|---|
| W-A33 | `v3-coder.md:18` | "You implement exactly the change the task names — **the task is the spec**. You never \"improve\" adjacent code, never redesign what you were asked to patch" | intent | `CQ "DO NOT fucking touch a part i have not asked you about"` → 07-30 | — | unreviewed |
| W-A34 | `v3-coder.md:42` vs `maths-algorithmist.md:47` | "Do not run `refresh_graph.py`, `graphify --update`, or `/critical-review` yourself" **versus** "**After any edit** under `v3/` or to root canon, run `python refresh_graph.py`" | intent | Two definitions give opposite orders on the same script, and the second also contradicts `CLAUDE.md`'s "never per-edit" (W-C20). `CQ "graphify"` → nothing in the record sets either policy | **[AGENT-ORIGIN]**, mutually inconsistent (3.10) | unreviewed |
| W-A35 | `code-optimizer.md:40` | "run `python refresh_graph.py` after repo edits and process any worklist; run the repo's `/critical-review` on changed `v3/` files" | intent | Third instance of the per-edit refresh rule; `CQ "critical.?review"` → **0 hits** (verified) | **[AGENT-ORIGIN]** (3.10, 1.7) | unreviewed |
| W-A36 | `retrieval-scientist.md:60` | "After changing files, run `python refresh_graph.py` from the repo root (never `graphify --update`) and process any worklist. After writing or changing v3 code, run /critical-review" | intent | Fourth instance | **[AGENT-ORIGIN]** (3.10, 1.7) | unreviewed |
| W-A37 | `graph-refresher.md:30` | "`REFRESH.md` is the procedure canon. Follow it exactly; **if this definition and REFRESH.md ever disagree, REFRESH.md wins** and your report says so." | intent | An agent-written procedure doc given precedence over an agent-written role doc. `ls graphify-out/REFRESH.md`; `git log --oneline -- graphify-out/REFRESH.md` for authorship | **[AGENT-ORIGIN]** (3.11) | unreviewed |
| W-A38 | `graph-refresher.md:53` | "NEVER run `graphify --update`. `refresh_graph.py` is the single rebuild authority." | state + intent | State: does `--update` actually drop the external-doc bridges? `grep -n "external_cache\|bridge" refresh_graph.py`. Intent: `CQ "graphify"` → 3 hits, none about rebuild paths | **[AGENT-ORIGIN]** (1.8) | unreviewed |
| W-A39 | `graph-refresher.md:46` | "**Node-drop guard** (`refusing to write ... >10% drop`): STOP. Never pass `--force` on your own authority" | state | `grep -n "force\|drop" refresh_graph.py` — confirm the guard exists and the threshold is 10% | — | unreviewed |
| W-A40 | `graph-refresher.md:49` | "`! external folder missing: <path>` for an absent `docs/handoff` is a known harmless note on this machine" | state | `ls docs/handoff 2>&1` (W-C16) | — | unreviewed |
| W-A41 | `eval-statistician.md:20` | "Tests you run: exact permutation (sign-flip) test on paired mean differences; Wilcoxon signed-rank …; McNemar for binary outcomes; paired bootstrap (BCa, >=10,000 resamples, seeded) for CIs." | intent | `CQ "significan\|p.value\|permutation"` — is this battery the user's requirement or the agent's methodology? It may be good statistics and still be agent-origin | — | unreviewed |
| W-A42 | `eval-statistician.md:23` | "10smoke has 2^10 = 1024 sign-flip permutations, so the exact-p floor is ~0.001 … n=10 supports \"the sign of a big effect\", never per-type claims" | state | Arithmetic: 1/1024 ≈ 0.00098. Verifiable without data | — | unreviewed |
| W-A43 | `eval-statistician.md:23` | "Gold-100 per-type cells: **company n=5 and url n=1 are anecdotes** — you refuse inference on them" | state | **[user-gated]** — route via per-type counts in a gold-100 run's `eval_results.jsonl`, never by opening `gold100.jsonl`. Note `v3/output/DATA_README.md` §Question sets records held-out-100 at url n=19, so the rule is set-specific and the agent line does not say so | — | unreviewed |
| W-A44 | `eval-statistician.md:49` | "For any proposed run calling a claude-* model: compute tokens-per-call x calls x concurrency … state the total and the subscription-window impact out loud … **This is a hard rule with no de-minimis exception.**" | intent | `CQ "burned almost my entire usage in 30 seconds"` → 07-17; `CQ "burned 70% usage"` → 07-23; `CQ "waste all my usage"` → 07-24. The documented tension: `CQ "0 fucks given"` → 06-18, where the user said the opposite. Rule on which governs | **[GROUNDED]**, with a documented tension (3.7) | unreviewed |
| W-A45 | `eval-statistician.md:49` | "**You design judge runs; you do not launch them.**" | intent | `CQ "let ME be the one"` → L173, 07-16T07:40 (verified) | **[GROUNDED]** (3.8) | unreviewed |
| W-A46 | `critical-reviewer.md:46` | "**No model calls.** Never invoke `nim.py`, the claude/codex/gemini CLIs, or anything that spends a judge or generator token. **Reviews cost zero.**" | intent | Same burn evidence as W-A44 | — | unreviewed |
| W-A47 | `code-optimizer.md:50` | "multiprocessing on win32 is **spawn-only**: `if __name__ == \"__main__\"` guards, and the pickle + interpreter-startup tax is measured before any parallel claim." | state | Platform fact, verifiable: `python -c "import multiprocessing as m;print(m.get_start_method())"` | — | unreviewed |
| W-A48 | `code-optimizer.md:49` | "Benchmark inputs stay byte-exact — **the artefact arm hash-verifies raw files.** Never mutate `v3/data/`" | state | `grep -rn "sha256\|hash" v3/artefact/scan.py v3/artefact/resolver_prototype.py`; `git check-attr text -- v3/data/x` for the `-text` rule | — | unreviewed |
| W-A49 | `results-analyst.md:54` | "the artefact gold-100 run's recorded generator input **excludes cache reads and massively undercounts**" | state | Read `run_manifest.json` token fields from the gold-100 artefact dir and compare against context sizes in `arm_outputs.jsonl` | — | unreviewed |
| W-A50 | `v3-coder.md:52` | "Do not write report/summary/analysis .md files; findings go in your final message." | intent | `CQ "not reading that\|writing too fucking much"` — supports terseness; check whether it supports a file prohibition specifically | — | unreviewed |

---

## Tier 4 — `v3/README.md` (28 claims)

The `## Decided` heading is what puts this file here: every line under it is asserted as ruled.
The audit adjudicated 12; 16 are new.

| id | claim | kind | check | audit prior (one agent's opinion) | status |
|---|---|---|---|---|---|
| W-R01 | Banner: "`docs/canon/CANON_AUDIT.md` checks 117 prescriptive claims … of which **12 come from this file**." | state | Count rows 2.1–2.12 at `CANON_AUDIT.md:308-322` | — | unreviewed |
| W-R02 | "The system under test is the modified v1 artefact, querying the `herb-eval` graph … They are **two configurations of the system under test, not baselines** … Which leg is the reported artefact configuration is undecided" | intent + state | Intent: `CQ "NOT doing the v3 artefact"` → L588 for the v1-not-v3 half; `CQ "which artefact that is even the baseline"` → 07-29 for the undecided half. State: `grep -n "DATABASE" v3/pipelines/artefact_v1.py`. The claim this replaced named the arm `artifact` and called it "built natively in v3" | **[CONTRADICTS-USER]** + self-violating on the replaced wording (2.1) | unreviewed |
| W-R03 | "the arms share **nothing** — each reads, indexes and ranks the corpus with its own code … they share no retrieval code with each other, and nothing with the artefact." | state | `grep -rn "^from\|^import" v3/pipelines/*.py` — look for shared retrieval imports beyond `contract`/`nim` | **[GROUNDED]** (2.11) | unreviewed |
| W-R04 | "The deterministic backbone is **ID-based** context precision/recall against the gold citations (`IDBasedContextPrecision` / `IDBasedContextRecall`, no judge)" | state | `grep -n "IDBasedContext" v3/eval/ragas.py v3/eval/ragas_catalog.py` | — | unreviewed |
| W-R05 | "`context_precision_llm_ref` stays commented out because it is ~k judge calls per question and turns the slow lane into the whole run." | state | `grep -n "context_precision_llm_ref" v3/eval/ragas_catalog.py` — confirm it is commented | — | unreviewed |
| W-R06 | "GPT judge runs use the signed-in Codex CLI …, not `OPENAI_API_KEY`. Gemini judge runs use the signed-in Gemini CLI, not an API key." | state | `grep -n "codex\|gemini\|OPENAI_API_KEY" v3/eval/ragas.py` | — | unreviewed |
| W-R07 | "`data/corpus/` — oracle stripped out. **Pipelines see only this**, and only via a truth-free prompt." | state | `grep -rn "data/raw\|data/corpus" v3/pipelines/*.py` — any pipeline path reaching raw is a quarantine breach. Note the 07-28 audit's finding that the artefact arm resolves chunk text from full raw HERB at answer time (W-M62's leakage paragraph) | — | unreviewed |
| W-R08 | "`data/raw/` — full HERB; the ~1514 questions + ground_truth + citations live inside the product files. **Evaluators read truth from here, in place.**" | state | `grep -n "data/raw" v3/eval/ragas.py v3/questions.py` — reader side only | — | unreviewed |
| W-R09 | "`metadata/` (employee / customer / team directories) stays on both sides — it's legitimate retrieval data, not oracle." | intent | `CQ "metadata\|oracle"` — is the metadata carve-out the user's ruling? | — | unreviewed |
| W-R10 | — | "`pipelines/` — `artifact.py`, `lucene.py`, `vector.py`." | state | `ls v3/pipelines/` → the file list now names `artefact_v1.py`, `artefact_v1_det.py`, `lucene.py`, `vector.py`, `hybrid.py`, `artefact.py`, which is what the directory holds. Nothing asserts the old list | **[STALE]** — same defect as 1.11 | resolved — claim gone |
| W-R11 | "`build_question_sets.py` writes … `question_ids.gold100.jsonl` — the **gold-100**, a balanced answerable subset drawn by seeded round-robin over the HERB types (equal allocation, ~20/type)." | state | **[user-gated]** on the direct read. `project_benchmark_validity_caveats.md` says the set actually run is 22/55/17/5/1, "NOT the equal 20-per-type draw". Two live surfaces describe the same file incompatibly — settle via per-type counts in a gold-100 run's `eval_results.jsonl` | — | unreviewed |
| W-R12 | "Equal allocation … does not match HERB's natural mix, so report per-type and don't compare the gold-100 aggregate to HERB's published average." | intent | `CQ "academic"` → 06-27 *"this is an academic effort"*; the specific caveat is the agent's analysis, correct or not | **[GROUNDED]** in spirit, **[AGENT-ORIGIN]** as written (2.10) | unreviewed |
| W-R13 | "RAGAS is the only scorer, and nothing it reports is leaderboard-comparable against HERB's published figures — accepted, not a gap to close." | intent | `CQ "only RAGAS\|ONLY RAGAS"` → **0 hits** (verified). The audit cites 06-25 "twice and emphatically" — 06-25 is inside the 05-29→06-26 blackout, so this is a `[DOC]` recovery from `desktop_docs_record.md`, not chat. Cross-check: `grep -n "ONLY RAGAS" docs/canon/raw/desktop_docs_record.md`. For the second half: `CQ "herb score"` → 08-04 *"we have never used the herb score and has no intention to"*. Verdict on the first half is `cannot-determine` on chat alone | **[GROUNDED]** (2.2) — cited to a quote absent from the corpus | unreviewed |
| W-R14 | "**k is shared; the retrieval budget it buys is not** — an artefact context is a graph chunk carrying ~10 artifact ids, a baseline context is one artifact carrying one" and "**Still open:** which framing of the matched-budget result ships … k is 50 and user-set" | intent + state | State: `grep -rn "k=50\|top_k" v3/run.py v3/orchestrator.py`, the `top_k` field in any `run_manifest.json`, and the per-question id counts in `v3/output/DATA_README.md` §"The unmatched-unit rule". Intent: `CQ "k=50 does not mean the same for all arms"` → 07-26, and `CQ "for academic rigor, we have done k=50"` → L217 for the value. The claim this replaced called the budget "shared" and the value "still open" | **[STALE]** on the replaced wording (2.3) | unreviewed |
| W-R15 | "**Generation and scoring are separate phases** (`questions` / `evals` / `full`), so iterating a scorer never re-runs the generator." | state | `grep -n "questions\|evals\|full" v3/run.py v3/orchestrator.py` — and reconcile with W-R21, which says the split has not happened | — | unreviewed |
| W-R16 | "the judged metrics use the default haiku judge (`claude-haiku-4-5`)" | intent | `CQ "try haiku first"` → 07-16; `CQ "we decided to use haiku"` → 07-29 | **[GROUNDED]** (2.4) | unreviewed |
| W-R17 | "**Per-question telemetry is split**: `ArmOutput.generator` … vs `ArmOutput.retrieval` (the arm's OWN retrieval-time model cost — vector's query embed; zero for lucene)." | state | `grep -n "generator\|retrieval" v3/contract.py` | — | unreviewed |
| W-R18 | "**Provenance** is two manifests — `RunManifest` … + `EvalManifest` …; **no seed, no git-sha**." | intent + state | State: `python -c "import json;print(list(json.load(open('v3/output/<dir>/run_manifest.json'))))"` — confirm no sha field. Intent: `CQ "traeability, reproducibility"` → 07-16T07:43, the user asking for exactly the property this decision removes | **[CONTRADICTS-USER]** (2.5) | unreviewed |
| W-R19 | "`qwen/qwen3.5-397b-a17b` on NVIDIA NIM **is still the shared generator** injected into all three arms" | intent + state | State: read `generator` from recent `run_manifest.json` files — several 2026-07-23+ runs used `claude-haiku-4-5` or sonnet. Intent: `CQ "why the fuck are we even using qwen"` → 07-19 | **[STALE]**, contested (2.6) | unreviewed |
| W-R20 | "Multilingual, so HERB now and **the deferred Swedish Bonnier set** run on the same generator, no swap." | intent | `CQ "Bonnier"` — the audit cites 06-14 *"the Bonnier set will have to wait"* (blackout window) | **[GROUNDED]** (2.7) | unreviewed |
| W-R21 | "(The orchestrator currently runs a single combined path; splitting it into the three modes is **the pending step** — see Still open.)" | state | `grep -n "retrieval-only\|no-eval\|--judge" v3/run.py` — the flags the user runs by name all exist; contradicts W-R15 in the same file | **[STALE]** (2.12) | unreviewed |
| W-R22 | "Not GPT-4o, so HERB's published baselines get **re-run, not cited**." | intent | `CQ "GPT-4o\|baseline"` — no user statement expected | **[AGENT-ORIGIN]** (2.8) | unreviewed |
| W-R23 | "**Generation contract — a thin, fixed RAG pipe.** … *\"Answer the question using only the provided documents. Be concise.\"* … held byte-identical across all three arms" | state | `grep -rn "Answer the question using only the provided documents" v3/` — one shared constant, or copies that can drift? | **[GROUNDED]** (2.9) | unreviewed |
| W-R24 | "**lucene arm built**: bm25s `method=\"lucene\"` … k1=0.9 / b=0.4 are the BEIR reference values … **all 17,087 gold citations resolve to an artifact `id`**" | state | `grep -n "k1\|b=\|method" v3/pipelines/lucene.py`. The 17,087 figure needs the gold citations — **[user-gated]**; route via corpus id counts instead | — | unreviewed |
| W-R25 | "**vector arm built**: embedder `nvidia/llama-nemotron-embed-1b-v2` … the 8192-token context covers every HERB artifact (longest ~1.5k tokens) … the ~38.6k-artifact corpus is too small to need [ANN]" | state | `grep -n "nemotron\|8192" v3/pipelines/vector.py`; count corpus artifacts: `python -c` over `v3/data/corpus/`. Note desktop memory names a different embedder id (W-E25) | — | unreviewed |
| W-R26 | "**Question ids minted deterministically** … `<product>::a\|u::<index>` … **815 answerable + 699 unanswerable = 1514**, unique, the paired-test join key." | state | **[user-gated]** — the counts live in `data/questions.jsonl`. Indirect: `grep -n "::a::\|::u::" v3/build_questions.py` for the minting rule; counts via `build_question_sets.py`'s own output files under `v3/output/` | — | unreviewed |
| W-R27 | "**Still open:** … Which set to run — gold-100 (built; seeded stratified draw) vs the full 815 + 699. Judge calibration subset size." | state | `ls v3/output/ \| wc -l` — 100+ gold-100 runs exist and a held-out 100 was added on 07-29. Check whether "which set to run" is still open in practice | — | unreviewed |
| W-R28 | "Answer-level scoring measures the whole pipeline, not retrieval alone — a strong generator can mask retrieval quality." | state | Consistent with `project_benchmark_validity_caveats.md`'s extraction-bottleneck finding (W-M54); check they agree | — | unreviewed |

---

## Tier 5 — everything else (40 claims)

Inert until someone opens it. Same claim, far less reach — which is exactly why these rank last
and not because they are more likely to be right.

### 5a — `v3/artefact/DESIGN.md` + `MODEL_CONTRACTS.md` (15)

The audit's finding here was that staleness is not the main problem — **unapproved content
written as settled is**. Note `CLAUDE.md` (W-C14) and `retrieval-scientist.md` (W-A27) both
declare these files stale while leaving them in the tree for the next agent to read.

| id | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|
| W-E01 | §14.7 "Matched literals are **stripped before the interpreter**" vs MODEL_CONTRACTS §2 "**marked spans, not stripped**" — while §5b lists that revision as status "**open**" | state | `grep -n "stripped\|marked spans" v3/artefact/DESIGN.md v3/artefact/MODEL_CONTRACTS.md`. An explicitly unapproved revision written into the contract body as settled prose | **[AGENT-ORIGIN]** — the pattern in its purest form (5.1) | unreviewed |
| W-E02 | §13.5 per-facet extraction spec — "This is what the v2 tagger prompt encodes per facet — the missing spec that caused v1 degradation" | state | `grep -n "facet" v3/artefact/tag.py` → `:4` "no facets (facets are measured later)" (verified); the built tagger emits a flat `{"tags": [...]}` | **[STALE]** — specified, never built (5.2) | unreviewed |
| W-E03 | §7 "Nothing else is a node" vs §13.1 "identities to `:Employee`/`:Customer` edges" and §9.6 "IDs, dates, and authors are now structural (**entities** + properties)" | state | `grep -n "Employee\|Customer\|entities" v3/artefact/DESIGN.md` | **[STALE]** — unremoved residue (5.3) | unreviewed |
| W-E04 | §11 tagger model `mistral-large-3-675b…`, justified by "**Swedish semantic fidelity (the Bonnier dataset)**" | state | `grep -n "mistral\|glm" v3/artefact/DESIGN.md v3/artefact/tag.py` — the built tagger uses `z-ai/glm-5.1`, and §12 of the same file defers Bonnier | **[STALE]** (5.4) | unreviewed |
| W-E05 | §13.4 table: function/TAM are **tag-facets** vs MODEL_CONTRACTS §1: function/TAM are "**chunk attributes, not tags, never embedded**" | state | `grep -n "TAM\|function" v3/artefact/DESIGN.md v3/artefact/MODEL_CONTRACTS.md` — three statements, two positions, one file | **[STALE]**, self-contradicting (5.5) | unreviewed |
| W-E06 | §9.1 "3000 is a calibration seed, **not a verdict**" vs §15 "the cap **is fixed by design** … what's open is only the empirical sweep" | intent | `CQ "3000\|calibration seed"` — audit cites desktop record 06-04 (blackout, `[DOC]`) | **[AGENT-ORIGIN]** drift (5.6) | unreviewed |
| W-E07 | §1 "the graph indexes references, it does not store copies" | intent | `CQ "i just want the fucking references\|dont even want the data loaded"` — audit cites desktop record 05-30 (blackout, `[DOC]`) | **[GROUNDED]** (5.7) | unreviewed |
| W-E08 | §7 "The graph is `Source → File → Chunk → Tag`. Nothing else is a node." | intent | `CQ "either they are nodes\|OTHER RANDOM FUCKING NODES"` — audit cites 06-12 (blackout) | **[GROUNDED]** (5.8) | unreviewed |
| W-E09 | §14.4 "**No hard filters anywhere in ranking**. Facets always *order*, never *filter*." | intent + state | Intent: `CQ "hard filter seems insane\|why have a gate"` → 07-15 (inside the covered window). State: `grep -n "HERB_TAG_FIRST" v3/pipelines/artefact_v1.py` → `:167`, `:174`, `:203` implement a tag *gate* (verified) — so the shipping code violates this design rule **and** the 08-01 instruction | **[GROUNDED]** — strongly (5.9); makes `HERB_TAG_FIRST` **ranked #2** | unreviewed |
| W-E10 | §14.9 "the embedding-axis-projection machinery … is dead (**it was never the user's design**)" | intent | `CQ "none of what you are saying now is a thought I have had"` — the audit calls this exemplary handling; check §11 still justifies the embedder by the dead machinery | **[GROUNDED]**, exemplary (5.10) | unreviewed |
| W-E11 | §4 stage 0 structural oracle quarantine | intent | `CQ "DONT INCLUDE THE FUCKING EVAL FILES"` / `CQ "dont fucking include the eval part"` (both blackout-window citations) | **[GROUNDED]** (5.11) | unreviewed |
| W-E12 | §9.5 "**No overlap**", §9.4 deterministic boundary detector, embedding-based chunking rejected | intent | `CQ "chunk\|overlap\|boundary"` — audit cites desktop record 06-03 (blackout) | **[GROUNDED]** (5.12) | unreviewed |
| W-E13 | §12 "The SQL-agent remains the comparison baseline" | state | `ls v3/pipelines/` → artefact / lucene / vector / hybrid; no SQL agent | **[STALE]** (5.13) | unreviewed |
| W-E14 | Both docs address a **`backend/v2/`** tree that no longer exists; DESIGN cites `v2_model_contracts.md`, MODEL_CONTRACTS cites `v2_artefact_rebuild_design.md` — neither filename exists | state | `ls backend 2>&1`; `git log --all --oneline -- "**/v2_model_contracts.md"` | **[STALE]** (5.14) | unreviewed |
| W-E15 | MODEL_CONTRACTS §0 "**No numbers cross the model boundary, either direction.**" | state | `v3/pipelines/artefact_v1.py:645` and `:774` (verified) — the shipping interpreter both requests and validates numbers | **[GROUNDED]** as canon, **[STALE]** as applied (5.15) | unreviewed |

### 5b — Desktop-memory claims (12 rows covering 30 audit claims)

These files are copies under `docs/canon/raw/desktop_memory/` on this machine and live memory on
the desktop. The **block decision** about whether to review the copies at all is `W-B01`; these
rows exist because the audit adjudicated the claims individually and they carry across machines.

| id | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|
| W-E16 | The 19 entries the audit passed as "grounded, verbatim-quoted, and correct — not itemised further": `graph-is-references-not-copies`, `v2-graph-spine`, `design-before-build`, `docs-track-reality`, `heed-user-intent-not-correct-it`, `no-silent-fallbacks`, `no-cutting-corners`, `delete-dont-preserve`, `check-existing-before-adding`, `code-readability-plain-naming`, `lock-concept-language`, `match-output-to-the-ask`, `memory-is-downstream-of-conversation`, `user-owns-execution`, `state-handoff-utmost-care`, `thesis-is-done`, `data-layout-storage-vs-working`, `no-fabricated-offline-checks`, `verify-before-asserting` | intent | **One row, 19 claims, deliberately.** The audit itself never itemised them — it passed them as a list, which is the same batch verdict `REVIEW_PROTOCOL.md` forbids. Ruling needed: split into 19 rows and check each quote in the corpus, or accept the audit's lump. Most sit in blackout windows, so expect `cannot-determine` on chat alone | **[GROUNDED]** ×19, un-itemised (surface 6 subtotal) | unreviewed |
| W-E17 | `v3-arm-model-stack.md`: "**Why this overrides the earlier 'ground references' the user pasted:** that note named `all-MiniLM-L6-v2` … Dropped" | intent | An agent recording in writing that it overrode source material the user handed it. `CQ "MiniLM\|ground reference"` | **[CONTRADICTS-USER]** in method (6.1) | unreviewed |
| W-E18 | `no-cost-estimates.md`: "Cost (time or money) must carry **ZERO weight** in my own reasoning, recommendations, or option-comparisons." | intent | `CQ "0 fucks given"` → 06-18 (grounded at origin), then `CQ "burned almost my entire usage\|burned 70% usage\|waste all my usage"` → 07-17, 07-23, 07-24. A fresh agent reading desktop memory and not laptop memory reinstates the behaviour that caused three of the worst incidents | **[STALE]** — dangerously so (6.2) | unreviewed |
| W-E19 | `project_overview.md` "**RAGAS ONLY** … there is **NO separate HERB scorer** … do not reintroduce it" vs `v3-arm-model-stack.md` "**Scoring is HERB + RAGAS only**" | intent | Same as W-R13 — `CQ "only RAGAS"` → 0 hits; the ruling is a `[DOC]` recovery | **[STALE]** cross-file conflict (6.3) | unreviewed |
| W-E20 | `herb-eval-arm.md` states, in one file, both "**context_ids are real**" and "**`context_ids` is empty**"; and both "the v1 full-text fallback is **DELETED**" and "**Gated full-text fallback kept**" | state | `grep -n "context_ids" docs/canon/raw/desktop_memory/herb-eval-arm.md`; settle against the code: `grep -n "context_ids" v3/pipelines/artefact_v1.py` | **[AGENT-ORIGIN]** — internally incoherent (6.4) | unreviewed |
| W-E21 | `retriever-routing-model.md` "Embedder is chosen: `nvidia/llama-3.2-nv-embedqa-1b-v2`" vs `nvidia-llm-host.md` / `v3-arm-model-stack.md`: `nvidia/llama-nemotron-embed-1b-v2` | state | `grep -n "embed" v3/pipelines/vector.py` settles which ships; `CQ "NEMOTRON"` → 06-28 *"fs,. i just said it's NEMOTRON FFS!"* | **[STALE]** (6.6) | unreviewed |
| W-E22 | `v3-artefact-subsystem.md` "`herb-eval` … **never queried live**" vs `herb-eval-arm.md`, an entire arm that queries it live | state | `v3/pipelines/artefact_v1.py:117` (verified) | **[STALE]** (6.7) | unreviewed |
| W-E23 | `docs-track-reality.md`: "this project uses **AGENTS.md**, not CLAUDE.md, as the auto-loaded brief" | state | `ls AGENTS.md 2>&1` → no such file at the repo root. An agent following this writes canon into a file nothing reads | **[STALE]** — actively misleading (6.8) | unreviewed |
| W-E24 | `facet-semantic-framework.md` "The facet set is **settled**: topic, process, stance, communicative-function, time" vs `tag-facets-vs-routing.md` "**Topic is not a facet**" vs `retag-facet-analysis.md` "**All five facets are RESTORED**" (topic/entities/activity/temporal/evidence) | state | Three files, three incompatible "settled" facet sets. `grep -rn "facet" docs/canon/raw/desktop_memory/ \| head -30`; settle against code (W-M37) and against `project_source_of_truth.md`'s five (W-M42) | **[STALE]** — three settled answers (6.5) | unreviewed |
| W-E25 | `retag-facet-analysis.md` names "deepseek-v4-pro" as the v2 tagger host; `v3-artefact-subsystem.md` names `meta/llama-3.3-70b-instruct` for the interpreter; DESIGN §11 names Mistral Large; the built tagger is `z-ai/glm-5.1` | state | `grep -rn "model" v3/artefact/tag.py v3/artefact/interpreter.py` — four model names for two roles | **[STALE]** (6.9) | unreviewed |
| W-E26 | `artefact-pass2-design.md`: "hub nodes for shared field values in a mid-selectivity band" vs `v2-graph-spine.md`: "The minted hub-node-per-label idea is **dead**" | state | The pass-2 file names the tension itself and asks for explicit sign-off — the audit calls this the correct handling. Ruling needed on the design, not on the documentation | **[AGENT-ORIGIN]**, honestly flagged (6.10) | unreviewed |
| W-E27 | `no-claude-attribution.md`: "Never include … AI/Claude attribution … **This is the user's master's thesis** … must read as the user's own" | intent | Same split as W-M14/W-M15: rule unsupported in the surviving record (blackout-plausible → `cannot-determine`); thesis rationale contradicted by `CQ "drop the fucking thesis"`. The sibling file `thesis-is-done.md` records the opposite — two desktop files disagree | Rule **[AGENT-ORIGIN]**; rationale **[CONTRADICTS-USER]** (6.11) | unreviewed |

### 5c — The state docs (8)

| id | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|
| W-E28 | `USER_CANON.md` in its entirety — 469 quotes, verbatim and correctly dated | state | Sample 15 quotes at random and match each against `user_turns_all.jsonl` by corpus line. **Critical**: 115 entries are second-hand `[DOC]` recoveries, not chat — count them and check they are visually distinguishable. W-C10 and W-R13 are two cases where a `[DOC]` quote is cited elsewhere as if it were chat | **[GROUNDED]** — "the one clean surface" (7.1) | unreviewed |
| W-E29 | `USER_CANON.md`: "**THE MISSING PERIOD IS NOT MISSING — IT IS IN GIT. GO READ IT.** … An earlier agent repeatedly claimed provenance was lost; it never was." | intent | `CQ "GIT REPO HAS ALL THE FUCKING HISTORY"` → 08-02T22:42. Directly overturns memory entry W-M03 | **[GROUNDED]** (7.2) | unreviewed |
| W-E30 | `2026-07-22-v1-curve-walk-facets-and-cluster-k.md` §8 declared "**binding**" by `maths-algorithmist.md` | intent | Same as W-A20 | **[AGENT-ORIGIN]** (7.3) | unreviewed |
| W-E31 | `2026-07-28-audit-absorption…md` — the five-reviewer verdicts, the full revert, "topic ≠ evidence" | intent + state | Intent: `CQ "there is no semi-revert option"` → 07-28. State: `git log --oneline -5` and `git show 5006fed --stat \| head` | **[GROUNDED]** (7.4) | unreviewed |
| W-E32 | State docs recording "**the user's verdicts**" on mechanisms (chord break, value-knee) | intent | Same as W-M69/W-A21 — `CQ "walk and the .best fit"` returns a question, not a ruling | **[CONTRADICTS-USER]** in attribution (7.5) | unreviewed |
| W-E33 | `2026-08-02-benchmark-validity-record.md`, `2026-08-02-corpus-facts.md` — recent, measured, caveated | state | `ls "C:/Users/jocke/OneDrive - Högskolan Dalarna/Coding/state-transfer/GRAG-Job/2026-08-02-"*.md` and spot-check two numbers each against `v3/output/` | **[GROUNDED]** (7.6) | unreviewed |
| W-E34 | `CLAUDE.md`'s pointer to `docs/state/…` | state | Same as W-C12 / W-C17 | **[STALE]** (7.7) | unreviewed |
| W-E35 | `2026-06-20-v3-contract-vector-arm.md` and the older docs framing v3/artefact as the artefact | intent | `CQ "NOT doing the v3 artefact"` → L588, 07-26 | **[STALE]** (7.8) | unreviewed |

### 5d — The `docs/canon/` documents themselves (5)

The audit adjudicates other surfaces. That does not lift it out of the pile, and neither does
this list lift itself out.

| id | claim | kind | check | audit prior | status |
|---|---|---|---|---|---|
| W-E36 | `CANON_AUDIT.md`'s counts: "65 GROUNDED, 17 AGENT-ORIGIN, 11 CONTRADICTS-USER, 24 STALE" across 117 claims, and the per-surface subtotal table at `:45-51` | state | Re-tally the verdict column of every row table and compare against the header. Also check the note "One verdict per claim; where a claim is grounded as a rule but stale in application, it is counted under the verdict that governs" — several rows carry two verdicts | — (self) | unreviewed |
| W-E37 | `CANON_AUDIT.md` presents `[DOC]` recoveries and `[CHAT]` quotes in the same italic-quote-plus-date format | state | **Verified failing on two rows already**: W-C10 (*"MY WORDS ARE THE CANON"*, 06-25) and W-R13 (*"this is ONLY RAGAS"*, 06-25) both return **0 corpus hits** and sit inside the 05-29→06-26 blackout. Count how many audit citations fall in blackout windows: any date in 05-16→05-26 or 05-29→06-26 is second-hand | — (self) | unreviewed |
| W-E38 | `docs/canon/README.md`: "**Nothing in this tier outranks anything else in it** — not by age, not by title, not by being cited elsewhere." | intent | `CQ "just because the text is in the repo"`. Then check the direct tension with `CLAUDE.md`'s W-C22, which makes `USER_CANON.md` the attribution gate — i.e. gives one interpretation-tier document authority over the others | — (self) | unreviewed |
| W-E39 | `docs/canon/README.md`: "**803 turns, 2026-05-14 → 2026-08-03** — laptop 676 + desktop 127, merged and deduped … 10,313 user-role turns seen, 9,547 rejected by rule … false-negative audit (0 of 6,380)" | state | `python -c "print(sum(1 for _ in open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8')))"` → **803** (verified). The filter's own accounting is in `raw/EXTRACT_REPORT*.md` — read it and judge how much intent the filter dropped | — (self) | unreviewed |
| W-E40 | `REVIEW_WORKLIST.md` (this file) in its entirety | state | Every row's check command must run and return what the row implies. Spot-check ten at random. A row whose check does not execute is a defect in this file, not in the surface it points at | — (self) | unreviewed |

---

## Block decisions (6)

The 85 memory copies and the 57 legacy worktree docs are **not** 142 rows. Each block gets one
row proposing a decision, and what ruling on it would settle.

| id | block | size | the proposal | what a ruling settles | status |
|---|---|--:|---|---|---|
| W-B01 | `docs/canon/raw/desktop_memory/` — copies of the desktop machine's memory, taken 2026-08-03 | 53 files | **Review the 12 adjudicated claims (W-E16…W-E27) and nothing else.** These are copies; the originals are live on the desktop, where they still auto-load. Reviewing the copy changes nothing on the machine that reads it | Whether desktop memory is in scope at all. If yes, the real work is on the desktop, not on these copies — and `no-cost-estimates.md` (W-E18) is the one that would reinstate three of the project's worst incidents | unreviewed |
| W-B02 | `docs/canon/raw/laptop_memory/` — copies of the 32 live laptop memory files, same snapshot | 32 files | **Do not review. Redundant with Tier 2**, which reviews the live originals at the path that actually auto-loads | Nothing more than confirming the copies are byte-identical to the originals: `python -c` sha256 both trees and diff the manifest | unreviewed |
| W-B03 | `.claude/worktrees/flamboyant-buck-4586c0/` — pre-v3 checkout, own AGENTS.md / backend / frontend doc set | 27 files | **Rule the whole tree superseded, or delete the worktree.** Dated 2026-05-17, describing the build the user quarantined. Nothing in the current pipeline reads it — but `AGENTS.md` files there are exactly the shape an agent picks up by accident | Whether these are kept as history or removed. Note `docs-track-reality.md` (W-E23) tells agents this project uses AGENTS.md — and these are the AGENTS.md files it would find | unreviewed |
| W-B04 | `.claude/worktrees/hardcore-engelbart-ea5bc5/` — second pre-v3 checkout, incl. `quarantine/DO_NOT_READ_UNLESS_LEGACY.md` | 30 files | **Same ruling as W-B03.** It already carries its own quarantine notice, which is the closest thing in the repo to a self-executing block decision | Same. `project_source_of_truth.md` (W-M41) names `docs/frontend/query_interpretation_layer.md` and `backend/tagging/pipeline.py` as authoritative — files that exist **here**, in a tree marked legacy | unreviewed |
| W-B05 | The 5 in-repo `docs/state/*.md` + 11 OneDrive state docs | 16 files | **Freeze as dated records; review only where a live surface declares one binding.** That is W-A20 (§8 binding) and W-M30 (§3 binding) — two rows, already in the list | Whether a dated state doc may ever bind a permanent agent. `CLAUDE.md`'s own rule says these are frozen descriptions of a moment (W-C28); two agent definitions override it | unreviewed |
| W-B06 | `v3/output/` — 129+ run folders with their manifests, plus `DATA_README.md` and `v3/artefact/data/README.md` | 130+ dirs | **Not interpretation — this is state, and it is the evidence other rows are checked against.** Do not review as claims. `DATA_README.md` is the exception: it is agent-written prose declared "binding" by five agent definitions (W-A13…W-A17) and belongs in the list on its own | Whether `DATA_README.md`'s validity table survives as a rule, and what happens to the invalid `__k` slice dirs and the partial 2026-07-23 `JUDGE_*` dirs the 07-28 audit flagged as unusable | unreviewed |

---

## Totals

| Tier | Rows | Audit-covered | New to this list |
|---|--:|--:|--:|
| 1 — `CLAUDE.md` | 50 | 20 | 30 |
| 2 — live laptop memory (32 files) | 70 | 18 | 52 |
| 3 — agent definitions (10 files) | 50 | 14 | 36 |
| 4 — `v3/README.md` | 28 | 12 | 16 |
| 5 — everything else | 40 | 53 (incl. 19 in one row) | 5 |
| B — block decisions | 6 | — | 6 |
| **Total** | **244** | **117** | **145** |

Tier 5 carries 53 audit claims in 40 rows because `W-E16` holds the 19 desktop-memory entries the
audit passed as an un-itemised list. Splitting it is itself a ruling (see that row).

*Nothing in this file is reviewed. Nothing in it is evidence. `REVIEW_PROTOCOL.md` governs how a
row leaves `unreviewed`, and only the user can move one.*

