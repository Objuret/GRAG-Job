# docs/canon — the evidence, the contradiction map, and the pile of documents that talk about them

> **Interpretation, produced 2026-08-03, unreviewed by the user.** An agent wrote this file and
> the documents beside it in a few hours; all are listed `unreviewed` in `REVIEW_REGISTER.md`.

Established 2026-08-03 to settle one question: what did the user actually say? Agent inventions
had been accumulating as rules — an agent wrote a term or a number, a later agent recorded it as
"the user's", a third enforced it as a hard rule. The standing instruction, given the day before:

> "i fucking demand you filter through every fucking memory and chatlog you have and find
> out everything I HAVE SAID, THOROUGHLY" — **2026-08-02**

> "Search the entire repo for exactly ALL information I (the user, fucking ME) i have
> conveyed, the actual things I ACTUALLY SAID: all conversations, memories, logs, docs,
> data, diffs, committs, changes, fixes and code.. that means you have to search the entire
> git-repo also with all the fucking branches etc" — **2026-08-02**

Read this file before anything else in `docs/canon/`.

**Two things carry the work.** `raw/user_turns_all.md` is the evidence — his 920 turns, the
only source of intent, cited by line. `CONTRADICTION_MAP.md` is the live list of where those
rulings and the system disagree, each collision layered, cited, and carrying what fixing it
takes: an engine change, a graph rebuild, a doc correction, or a ruling only he can give.
Everything else in this folder is reference, opened when a specific claim is in dispute.

## The record has an end date, and it is not today

**Check `raw/user_turns_all.jsonl`'s last timestamp before citing the corpus as the record.**
It is a snapshot, not a live feed: it holds what had been said when the extractor last ran, and
every ruling given after that exists in conversation only until someone writes it down.

```
python -c "import json; r=[json.loads(l) for l in open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8')]; print(len(r), r[0]['iso_timestamp'][:16], r[-1]['iso_timestamp'][:16])"
```

Keeping it current is two steps, both at commit time, and `CLAUDE.md`'s hard rules require them:

1. **The ruling lands in the file that owns it** — `CONTRADICTION_MAP.md` for a collision,
   `OPEN_DECISIONS.md` for something still open, the code or `v3/CONSTANTS.md` for a constant or
   a flag — before the reply goes out.
2. **The corpus is extended**, so it carries the turn itself. A ruling recorded only in an
   interpretation document is an agent's paraphrase with no source behind it, which is the
   condition the 08-02 mining order was given to end.

A corpus that stops being extended rebuilds the problem this folder exists to fix: surfaces
asserting what the user wants, with nothing underneath them.

**Extend by union. Never overwrite.** `tools/canon_extract.py` reads Claude Code transcripts, and
Claude Code deletes old ones — so the corpus is **not reproducible from its sources**. A re-run on
2026-08-05 gained 106 turns and lost one, 2026-07-06 08:07 (*"ok, exactly where are we with the
whole artefact concept/build?"*), whose session file is gone from disk; the committed corpus is
now its only copy. Union a fresh extraction into the committed one, account for every turn the
run drops, and only then write. A plain re-run silently destroys evidence, and the arithmetic in
`raw/EXTRACT_REPORT*.md` describes the pass that produced the file — it does not describe what a
later pass would produce.

## Three kinds of thing. None of them is "authority"

**Intent — what was supposed to be built.** The only source is the user's own typed turns:
`raw/user_turns_all.jsonl` · `.md`. Nothing else carries intent — not a document, not a commit,
not a memory file. **Its one honest caveat: a machine decided what counted as a human turn** —
across both machines 11,137 user-role records were seen and 10,244 were rejected by a named rule,
leaving 803 turns (full arithmetic below); the corpus has since been extended by union to 920, through 2026-08-05. The corpus begins 2026-05-14, with
chat blackouts 05-16 → 05-26 and 05-29 → 06-26. The rules, tallies, false-negative audits and
discard samples are in `raw/EXTRACT_REPORT*.md` and `raw/rejected_sample*.md`: audited, not
infallible.

**State — what actually exists.** The git history — commits, diffs, and the actual file contents
at each commit (`git show <sha>:<path>` returns the real bytes) — plus the code, the graph and the
run outputs under `v3/output/`. Re-run the command and you get the same answer; it is nobody's
opinion. State proves something was built; it does **not** prove it was intended, or correct. If
an agent misread the user and coded it, git records the misreading perfectly.

**Interpretation — claims about intent or state.** Every document in this project: the
documents in this folder, this file, `raw/git_record.md` and `raw/desktop_docs_record.md`,
`CLAUDE.md`, both READMEs, every state and handoff doc, every memory file on both machines, every
agent definition — everything written 2026-08-03 included. All of it unreviewed, each piece
holding only as far as its citations, each checked against intent and state before it is acted on.
**Nothing in this tier outranks anything else in it** — not by age, not by title, not by being
cited elsewhere. `CANON_AUDIT.md` adjudicates other documents; that does not lift it out of the
pile. It is one more agent's opinion, pending review.

**The asymmetry, and it is the whole point: state is evidence of drift from intent, never
justification for it.** "It is in the code" and "the commit says so" are not arguments — they are
the thing being questioned. Something built against the record is a finding, not a defence.

`REVIEW_REGISTER.md` lists the whole pile, one row per artifact, every row `unreviewed`. A state
doc, a memory entry, `CLAUDE.md`, an agent definition, this file — interpretation, none of it
intent.

> "you do understand that just because the text is in the repo, that doesnt mean i was the one
> that ok'd it or put it there, right? you literally put shit in writing and pretend its canon"
> — **08-02**

> "ok, you do realise "verified by me" means YOU verified? and not me?" — **08-02**

A statement being written in this repo is not evidence he said it. Only a `[CHAT]` quote is, and
a `[CHAT]` quote is checkable in the corpus.

## The files

| File | What it is | Standing |
|---|---|---|
| `raw/user_turns_all.jsonl` · `.md` | The corpus: 920 verbatim turns, both machines merged, chronological, no edits. | **Intent** — the only source of it (machine-filtered). |
| `raw/user_turns.*` · `raw/user_turns_desktop.*` | The two halves before merge — laptop 793 (from 07-06), desktop 127 (from 05-14). | **Intent** (machine-filtered). |
| `raw/EXTRACT_REPORT*.md` · `raw/rejected_sample*.md` | The filter's own accounting, **one pair per machine**: counts, per-rule rejects, byte-identity verification, false-negative audit, samples of what was thrown out. Every figure inside is for that machine alone; `_desktop` also carries the merge. | Tool output. Read it to judge how much intent the filter dropped. |
| `CONTRADICTION_MAP.md` | Every statement of his that something contradicts, layered (V1-GRAPH / V1-ENGINE / V1-ORIGINAL / V2-DESIGN / V3-NATIVE / CROSS) so cross-layer false collisions cannot appear: 12 live collisions with the remedy each needs, 12 tensions awaiting his judgement, 14 near-collisions scoping dissolves, and the standing uncontradicted record. | **Interpretation**, unreviewed. The live list — every entry checkable against the corpus line it cites. |
| `USER_CANON.md` | 469 quotes selected from the corpus and arranged into 13 design subjects, 10 working-relationship subjects, a 60-row timeline, a never-built inventory. Quotes verbatim; **the choosing, grouping and headings are agent judgement**, and 115 entries are second-hand `[DOC]` recoveries from agent-written docs rather than chat. | **Interpretation**, unreviewed. An index into the record, not the record. |
| `CANON_AUDIT.md` | 117 prescriptive repo claims adjudicated against the record — 65 GROUNDED, 17 AGENT-ORIGIN, 11 CONTRADICTS-USER, 24 STALE. | **Interpretation**, unreviewed. Verdicts are not rulings. |
| `OPEN_DECISIONS.md` | Unruled reversals, what was specified and never built, unanswered questions, the 17 instructions no agent surface carries, audit findings awaiting a ruling. | **Interpretation**, unreviewed. "Unresolved" is an agent's reading. |
| `DESIGN_HISTORY.md` | Git record + desktop design docs merged into one chronological design history. | **Interpretation**, unreviewed. Each claim holds as far as its citation. |
| `REVIEW_REGISTER.md` · `REVIEW_WORKLIST.md` · `REVIEW_PROTOCOL.md` · `NEW_SESSION_PROMPT.md` | The review apparatus: every agent-written document one row each all `unreviewed`, the claim-by-claim rows behind that register, the procedure for working them with him, and the starter prompt for such a session. | **Interpretation**, unreviewed, and in its own list. Reference — look a claim up here; nobody is expected to work the rows. |
| `raw/git_record.md` | Reconstruction from the git history alone: 74 commits, 91 reproduce commands, 18 numbered contradictions. | **Interpretation** over state. Re-run the commands. |
| `raw/desktop_docs_record.md` | 20 agent-written design/state docs, 05-25 → 07-12, ~150 recovered quotes, 80 labelled rulings. Source of the `[DOC]` entries. | **Interpretation**, second-hand. |
| `raw/desktop_memory/` · `raw/laptop_memory/` | Copies of both machines' memory files, taken 2026-08-03. | **Interpretation**, unreviewed — and frozen at that date: what each machine believed, evidence of it, not a surface to correct. |
| `tools/canon_extract.py` (repo root) | Regenerates the corpus from Claude Code transcripts. | The tool that produces the intent corpus. Read it to judge the filter. |

## The corpus arithmetic

Every figure below is a count of Claude Code transcript records, produced by
`tools/canon_extract.py` and reproducible from the files in `raw/`. The two machines were
extracted in separate passes and then concatenated, so **each machine has its own accounting and
the merged totals are the sums**. Nothing here is an estimate.

| | laptop | desktop | merged |
|---|---:|---:|---:|
| **User-role records seen** — every record with `type: "user"` in the scanned transcripts | 10,313 | 824 | **11,137** |
| **Rejected by a named rule** — machine-authored, not typed by the human | 9,547 | 697 | **10,244** |
| **Duplicates collapsed** — same turn replayed into a branch/resume copy of a session | 90 | 0 | **90** |
| **Kept as human-authored** — the corpus | 676 | 127 | **803** |
| Collapsed at merge time (cross-machine duplicates) | — | — | **0** |

**The identity, and it holds exactly in every column:**

```
seen = kept + rejected + collapsed
laptop    10,313 =   676 +  9,547 + 90
desktop      824 =   127 +    697 +  0
merged    11,137 =   803 + 10,244 + 90
```

It holds by construction, not by luck: the extractor counts one `seen` per user record and then
sends that record down exactly one of three exits — rejected by rule, collapsed as a duplicate,
or kept (`tools/canon_extract.py`, the pass-2 loop). There is no fourth outcome.

**What each number is *not*, since every published miscount so far has come from mixing these up:**

- **10,313 and 9,547 are laptop-only.** They are not merged totals. Quoting them as the caveat on
  the 803-turn corpus silently drops the desktop's 824 seen and 697 rejected.
- **10,313 − 9,547 = 766 is not a corpus size and never was.** It omits the 90 collapsed
  duplicates, which are subtracted from the same pool. 766 − 90 = 676, the laptop half. The
  desktop's 127 then brings it to 803. A bare subtraction of *seen minus rejected* is wrong
  wherever duplicates were collapsed.
- **"Merged and deduped" was wrong.** The merge removed nothing: 0 collapses, and the two halves
  share no `uuid`, no `(timestamp, text)` pair and no session. The 90 collapses happened *inside*
  the laptop extraction, upstream of its 676 — so 676 + 127 = 803 with no removal is exactly
  right, and the earlier wording implied a step that did not occur.
- **The 90 are branch/resume artifacts, not repeated messages.** All 90 matched on
  `(timestamp, text)` to the millisecond across sibling copies of one session; 0 matched on
  `uuid`. Genuinely repeated text survives — 14 distinct texts appear more than once in the
  corpus, 54 rows in total, each with its own timestamp.
- **The false-negative audits are per-machine and used different methods.** Laptop: the 6,380
  `harness_template` rejects were audited three ways, 0 human turns lost. Desktop: no
  `harness_template` reject exists, the 620 `tool_result` rejects provably carry zero characters
  of human text, and all 77 remaining rejects were read individually. Neither audit covers the
  other machine.

**Verifying it yourself**, from the repo root:

```bash
# corpus sizes: 803 / 676 / 127
wc -l docs/canon/raw/user_turns_all.jsonl docs/canon/raw/user_turns.jsonl \
      docs/canon/raw/user_turns_desktop.jsonl

# no residual duplicates: 803 rows, 803 uuids, 803 (timestamp, text) pairs
python -c "import json;r=[json.loads(l) for l in open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8') if l.strip()];print(len(r), len({x['uuid'] for x in r}), len({(x['iso_timestamp'],x['text']) for x in r}))"

# the halves partition the whole: {'laptop': 676, 'desktop': 127}
python -c "import json,collections;r=[json.loads(l) for l in open('docs/canon/raw/user_turns_all.jsonl',encoding='utf-8') if l.strip()];print(collections.Counter(x['machine'] for x in r))"
```

The per-machine `seen` and `rejected` figures are not recoverable from `raw/*.jsonl` — those files
hold only what was kept. They come from the extraction reports, whose per-rule tables sum to the
rejected totals (laptop 6,380 + 2,530 + 373 + 202 + 45 + 16 + 1 = 9,547; desktop 620 + 29 + 21 +
17 + 10 = 697). To regenerate them, re-run the tool — but note the laptop transcripts are **live
and still growing**, so a fresh run will report a larger `seen` than 10,313. The figures in this
table describe the 2026-08-03 snapshot that produced the corpus.

## Coverage, and where it stops

- **920 turns, 2026-05-14 → 2026-08-03** — laptop 793 + desktop 127, concatenated. Nothing was
  removed at merge time; the two halves do not overlap. See the arithmetic below.
- **Nothing before 05-14 survives as chat.** The first commit is 2026-05-07. That first week — the
  52-file Neo4j pipeline, the 12-entry decision log, the original graph schema, the controlled
  canonical vocabulary — **survives only as state, in the git history**. Read it with
  `git show <ref>:<path>`; `raw/git_record.md` has the refs and 91 reproduce commands. What was
  *intended* that week is unrecoverable.
- **Two chat blackouts:** 05-16 → 05-26 (11 days) and 05-29 → 06-26 (29 days), zero human turns on
  either machine. They hold the v2 pivot, the facet redesign, the closing of the graph spine, the
  death of the chunk description, the build gate, the eval-harness design and the RAGAS-only purge.
  **No chat is not no record** — 20 dated design docs (`raw/desktop_docs_record.md`) and git cover
  both windows: interpretation and state, never intent. Second-hand, but never absent.
- **Thin days are thin, not silent.** Seven of the 30 active days carry one to three turns:
  05-27 (1), 05-28 (1), 07-01 (3), 07-02 (2), 07-12 (3), 07-27 (2), 08-03 (2). Absence of a
  statement on a date proves nothing.
- An earlier agent called **2026-07-15 "the first day"** of the project — the earliest date in one
  partial local extract, wrong by two months. Do not repeat it.

## How to re-derive all of it

From the repo root, using the miniconda python (the repo `.venv` is dead):

```bash
# laptop half (676 turns) — defaults to the two local Claude Code project roots
python tools/canon_extract.py

# desktop half (127 turns) — transcripts copied to OneDrive on 08-03
python tools/canon_extract.py --machine desktop --name user_turns_desktop --no-sweep \
  --sources "C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\_desktop_transcripts\A--exjobbet-repo" \
            "C:\Users\jocke\OneDrive - Högskolan Dalarna\Coding\state-transfer\GRAG-Job\_desktop_transcripts\A--exjobbet-repo-frontend-src--claude-worktrees-keen-galileo-4baf46"

# merge into the 803-turn corpus
python tools/canon_extract.py --merge laptop=docs/canon/raw/user_turns.jsonl \
  desktop=docs/canon/raw/user_turns_desktop.jsonl --name user_turns_all

# spot-check kept turns byte-for-byte against their source transcripts
python tools/canon_extract.py --verify 15 --verify-floor 5 --name user_turns_desktop
```

`raw/` is **evidence, and read-only** — the corpus, the two hand-built records
(`git_record.md`, `desktop_docs_record.md`) and the memory copies alike. The corpus is
re-derived with the tool, never edited. The records and the copies are frozen at their date:
they are what was believed then, and a claim inside one that the corpus contradicts is settled in
`CONTRADICTION_MAP.md` by citing the turn that contradicts it — never by rewriting the record,
which erases the evidence the map rests on. The documents in this folder are the layer that gets
corrected.

## When you disagree with him

The record is what he said. It is not what an agent concluded he meant.

- About to state what he wants? **Find the quote first.** If there is no quote, say there is no
  quote.
- Where two of his quotes conflict, **both stand** — listed in `OPEN_DECISIONS.md` §1. Do not pick
  a winner, do not reconcile them in a doc, do not build to one and record the other as superseded.
- A conflict between the record and what you believe is correct is **raised as a question** in the
  conversation, in plain English — never resolved silently in code or in a doc.
- Never "correct" his current intent with an older note. What he names, he wants; that is the spec.
- **Do not open** `v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl` or `10smoke.jsonl`
  while doing design work — 08-02: *"honestly, you should not have the questions/gold available to
  you, there is 0% good that can come out of taht"*.
