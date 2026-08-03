# docs/canon — what the user actually said

Established 2026-08-03 to settle one question: what did the user actually say? Agent
inventions had been accumulating as canon — terms, numbers and rules an agent wrote,
a later agent recorded as "the user's", and a third enforced as a hard rule. The
standing instruction, given the day before:

> "i fucking demand you filter through every fucking memory and chatlog you have and find
> out everything I HAVE SAID, THOROUGHLY" — **2026-08-02**

> "Search the entire repo for exactly ALL information I (the user, fucking ME) i have
> conveyed, the actual things I ACTUALLY SAID: all conversations, memories, logs, docs,
> data, diffs, committs, changes, fixes and code.. that means you have to search the entire
> git-repo also with all the fucking branches etc" — **2026-08-02**

Read this file before anything else in `docs/canon/`.

## The files

| File | What it holds | When to read it |
|---|---|---|
| `USER_CANON.md` | 469 verbatim user quotes, machine-verified against the transcripts, in 13 design subjects + 10 working-relationship subjects, a 60-row dated timeline, and a never-built inventory. | Before stating what the user wants. Every time. |
| `OPEN_DECISIONS.md` | Everything genuinely unresolved: his own unruled reversals, what was specified and never built, his unanswered questions, the 17 instructions no agent surface carries, and the audit findings awaiting his ruling. | Before proposing design work, and before asking him anything. |
| `CANON_AUDIT.md` | 117 prescriptive repo claims adjudicated against the record — 65 GROUNDED, 17 AGENT-ORIGIN, 11 CONTRADICTS-USER, 24 STALE — with the ten most damaging ranked by work misdirected. | Before trusting CLAUDE.md, an agent definition, a memory entry, or a design doc. |
| `DESIGN_HISTORY.md` | The git record and the desktop design docs merged into one chronological design history — how each decision got here, not just what it is. | When a decision's lineage matters, or when the working tree no longer holds the thing you need. |
| `raw/user_turns_all.jsonl` · `.md` | The corpus: 803 verbatim human turns, both machines merged, chronological, no edits. | When exact wording or a timestamp matters. |
| `raw/user_turns.*` · `raw/user_turns_desktop.*` | The two halves before merge — laptop 676 (from 07-06), desktop 127 (from 05-14). | Only when you need to know which machine a turn came from. |
| `raw/EXTRACT_REPORT.md` · `raw/EXTRACT_REPORT_desktop.md` | Counts, per-rule reject tallies, byte-identity verification, and the false-negative audit of the one text-matching rule: 0 of 6,380. | When you doubt the corpus is complete. |
| `raw/rejected_sample.md` · `raw/rejected_sample_desktop.md` | What the filter threw out and which rule threw it. | Same. |
| `raw/git_record.md` | Forensic reconstruction from git objects alone: 74 commits, 91 reproduce commands, 18 numbered contradictions. | For the pre-chat era, and for anything cleared out of the working tree. |
| `raw/desktop_docs_record.md` | 20 agent-written design/state docs, 05-25 → 07-12, with ~150 recovered user quotes and 80 labelled rulings. | For the two chat blackouts. |
| `raw/desktop_memory/` (53 files) | The desktop machine's memory files — the best-attributed surface in the project, and stale in places. | With `CANON_AUDIT.md` §6 open beside it. |
| `tools/canon_extract.py` (repo root) | Regenerates the corpus from Claude Code transcripts. | To re-derive; see below. |

## Trust ordering

1. **Verbatim chat** — `raw/user_turns_all.jsonl`, tagged `[CHAT]` in `USER_CANON.md`. His own
   keystrokes, timestamped. Highest, always.
2. **Git blob** — a commit, diff, or file as it was actually written. First-hand about the code;
   terse and authorship-blind about intent.
3. **Agent-written doc that quotes him** — tagged `[DOC]`. Second-hand: the quote passed through
   an agent's transcription.
4. **Any doc's claim about itself** — "decided", "settled", "binding", "canon", "verified". Not
   evidence of anything.

**An agent's own output is not canon.** Not a state doc, not a memory entry, not CLAUDE.md, not an
agent definition, not this file.

> "you do understand that just because the text is in the repo, that doesnt mean i was the one
> that ok'd it or put it there, right? you literally put shit in writing and pretend its canon"
> — **08-02**

> "ok, you do realise "verified by me" means YOU verified? and not me?" — **08-02**

A statement being written down in this repo is not evidence he said it. Only a `[CHAT]` quote is.

## Coverage, and where it stops

- **803 turns, 2026-05-14 → 2026-08-03** — laptop 676 + desktop 127, merged and deduped.
- **Nothing before 05-14 survives as chat.** The first commit is 2026-05-07. That first week — the
  52-file Neo4j pipeline, the 12-entry decision log, the original graph schema, the controlled
  canonical vocabulary — **survives only in git**. Read it with `git show <ref>:<path>`;
  `raw/git_record.md` has the refs and 91 reproduce commands.
- **Two chat blackouts:** 05-16 → 05-26 (11 days) and 05-29 → 06-26 (29 days), zero human turns on
  either machine. They hold the v2 pivot, the facet redesign, the closing of the graph spine, the
  death of the chunk description, the build gate, the eval-harness design and the RAGAS-only purge.
  **No chat is not no record** — both windows are substantially covered by 20 dated design docs
  (`raw/desktop_docs_record.md`) and by git. Treat that material as second-hand, never as absent.
- **Thin days are thin, not silent.** 05-27, 05-28, 07-02, 07-12 and 07-27 carry one to three turns
  each. Absence of a statement on a date proves nothing.
- An earlier agent called **2026-07-15 "the first day"** of the project. It was the earliest date in
  one partial local extract, wrong by two months. Do not repeat it.

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

`raw/` is **read-only**. Do not edit it — re-derive. `git_record.md`, `desktop_docs_record.md` and
the four top-level documents are built by hand from that evidence and cannot be regenerated by the
tool; correct them by re-reading the evidence, never by editing `raw/`.

## When you disagree with him

The record is what he said. It is not what an agent concluded he meant.

- About to state what he wants? **Find the quote first.** If there is no quote, say there is no
  quote.
- Where two of his quotes conflict, **both stand.** They are listed in `OPEN_DECISIONS.md` §1. Do
  not pick a winner, do not reconcile them in a doc, do not build to one and record the other as
  superseded.
- A conflict between the record and what you believe is correct is **raised as a question**, in
  plain English, in the conversation. It is never resolved silently in code or in a doc.
- Never "correct" his current intent with an older note. When he names something he wants, that is
  the spec.
- **Do not open** `v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl` or `10smoke.jsonl`
  while doing design work — 08-02: *"honestly, you should not have the questions/gold available to
  you, there is 0% good that can come out of taht"*.
