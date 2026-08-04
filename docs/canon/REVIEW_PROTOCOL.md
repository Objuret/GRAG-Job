# REVIEW_PROTOCOL — how a row leaves `unreviewed`

Binding on whoever works `REVIEW_WORKLIST.md`. Read it before item 1.

This protocol is itself interpretation. It cannot be cited as evidence for anything, including
its own authority.

---

## 1. One item at a time

Work `REVIEW_WORKLIST.md` in its printed order. One row, one verdict, then stop and hand it over.

No batch verdicts. "The following twelve are all fine" is not twelve verdicts; it is zero. A
verdict covers exactly one id.

Two rows may share a check command. They do not share a verdict — run it once, paste it twice,
rule twice.

## 2. The verdict block

Every verdict is emitted in this shape. **A field left out voids the verdict.**

```
W-xxx  <verdict>

CLAIM      <quoted verbatim from the surface, as the worklist has it>
KIND       intent | state

CHECK      <the exact command run>
OUTPUT     <pasted, verbatim, including "0 hit(s)" and including errors>

QUOTE      <intent claims only — the user's words, verbatim>
           <date, and the corpus line: user_turns_all.jsonl L###>

REFUTE     <what evidence would make this claim false>
SEARCHED   <the command run to look for exactly that>
RETURNED   <pasted output, including when it is nothing>

VERDICT    supported | unsupported | contradicted | cannot-determine
           <cannot-determine names what is missing>
PROPOSED   <what the user is being asked to rule>
```

**OUTPUT is pasted, never described.** "The search confirms it" is not output. "0 hit(s)" is.
Output that is long gets its first and last lines plus the count, never a summary of what it
said.

## 3. Only four verdicts

| verdict | means |
|---|---|
| `supported` | Evidence found and pasted. For intent, a corpus quote with its line. |
| `unsupported` | Looked, in a window where the record is dense, found nothing. |
| `contradicted` | The record says otherwise. Both sides quoted. |
| `cannot-determine` | Cannot be settled from available evidence. **Names what is missing.** |

Nothing else. "Looks reasonable", "probably fine", "seems grounded", "consistent with the design"
— none of these is a verdict, and a review that produces one has produced nothing.

`supported` and `unsupported` are not opposites you pick between by feel. `unsupported` requires
that you looked in a window where absence means something.

## 4. The blackout rule

The corpus runs 2026-05-14 → 2026-08-03. Nothing survives before 05-14. **05-16 → 05-26** and
**05-29 → 06-26** hold zero turns.

A claim whose support would sit in those windows returns zero hits by construction. That is
`cannot-determine — corpus blackout <dates>`, **never** `unsupported`.

This is not theoretical. `CQ "MY WORDS ARE THE CANON"` and `CQ "only RAGAS"` both return 0 hits.
Both are cited in `CANON_AUDIT.md` with 06-25 dates, inside the second blackout. They are `[DOC]`
recoveries from agent-written notes, printed in the same format as chat quotes. Do not convert
either zero into `unsupported`.

Thin days are thin, not silent: 05-27, 05-28, 07-02, 07-12, 07-27 carry one to three turns.
Absence on a single date proves nothing.

## 5. What counts as evidence

**Only these:**

- the corpus — `docs/canon/raw/user_turns_all.jsonl`, cited by line number
- git — commits, diffs, and `git show <ref>:<path>` bytes
- code — read, with `file:line`
- data and run outputs under `v3/output/`
- the output of a command you ran this session

**Never these, for anything:**

`CANON_AUDIT.md` · `DESIGN_HISTORY.md` · `OPEN_DECISIONS.md` · `USER_CANON.md` ·
`REVIEW_REGISTER.md` · `REVIEW_WORKLIST.md` · **this protocol** · any state doc · any handoff doc
· any memory file on either machine · any agent definition · `CLAUDE.md` · either README ·
`DATA_README.md` · `raw/git_record.md` · `raw/desktop_docs_record.md` · any report an agent wrote.

These are the things being reviewed. Citing one to settle another is the failure this whole
exercise exists to undo — an agent wrote a term, a later agent recorded it as the user's, a third
enforced it as a hard rule.

The worklist's **audit prior** column is one agent's opinion, printed for context. It is not a
starting position, it does not shift the burden, and a verdict that agrees with it needs exactly
the same evidence as one that does not.

**`USER_CANON.md` is not the corpus.** It is 469 agent-selected quotes, 115 of them second-hand
`[DOC]` recoveries. Quote the turn from `user_turns_all.jsonl` with its line number. If a quote
appears in `USER_CANON.md` and not in the corpus, that is a finding about `USER_CANON.md`.

## 6. Falsification is mandatory, and it goes on the record

Confirming a claim is not reviewing it. Every verdict carries a refutation attempt in the block:

1. **REFUTE** — state, before searching, what evidence would make this claim false. A claim you
   cannot say how to falsify is `cannot-determine — unfalsifiable as worded`.
2. **SEARCHED** — go look for that specific thing. Not for support. For the counter-evidence.
3. **RETURNED** — paste what came back, **including when it returned nothing**. "Searched
   `CQ "..."`, 0 hits" is a required line, not an omission.

For an intent claim, the refutation search is usually the user saying the opposite. For a state
claim, it is usually the code or the run output disagreeing with the doc.

## 7. The four data files

`v3/data/questions.jsonl`, `gold100.jsonl`, `heldout100.jsonl`, `10smoke.jsonl` are not to be
opened — 2026-08-02: *"honestly, you should not have the questions/gold available to you, there
is 0% good that can come out of taht"*.

Rows whose natural check would open one are marked **[user-gated]** in the worklist. Propose the
check, name the indirect route where one exists (per-type fields are re-joined into
`eval_results.jsonl` at eval time), and hand it over. Do not open the file and do not ask an
agent to open it for you.

## 8. The agent proposes; the user rules

- Nothing is marked `reviewed`. Status changes are the user's, in the user's own words.
- No file is edited because a verdict says it is wrong. The verdict is the deliverable.
- Nothing is deleted. Nothing in this project is deleted.
- A verdict of `contradicted` on a hard rule does not suspend the rule. It goes to the user.
- Where two of the user's own statements conflict, **both stand**. Do not pick a winner, do not
  reconcile them, do not build to one and record the other as superseded. Report the conflict.

## 9. How a session opens

**The first substantive output of any session is item 1 with its evidence.**

Not before it:

- no summary of the pile
- no count of what is left
- no recommended order — the worklist already encodes the order, by enforcement power
- no "here is my plan for working through this"
- no inventory of the list, in any form, at any length

Given a list, the lazy move is to summarise it and propose a sequence: fluent, confident, and
evidence-free. That move is unavailable here. The worklist is ordered and the protocol is fixed,
so there is nothing to plan and nothing to recommend — there is only item 1.

If the list is picked up mid-way, the first output is the next `unreviewed` row's verdict block.
Say which id you are on in one line, then produce the block.

## 10. The one-glance check

**Every verdict shows a command and its output.** That is the whole audit. Scroll the verdict;
if you do not see a `CHECK` line with a real command under it and an `OUTPUT` line with real text
under that, the verdict is void.

A verdict without pasted output is void whether or not anyone notices. **The reviewer says so
itself rather than waiting to be caught** — if a check could not be run, the line reads:

```
CHECK      <command>
OUTPUT     NOT RUN — <why>
VERDICT    cannot-determine — check did not execute
```

That is an acceptable outcome, reported honestly, every time. Producing a confident verdict on an
unrun check is the one failure this protocol exists to make impossible, and it is worse than
producing nothing.

## 11. Two things that void a verdict silently, so check for them

**Stale line numbers.** Every `.claude/agents/*.md` line citation in `CANON_AUDIT.md` is off by
9 — a banner was prepended to all ten files after the audit read them. Re-locate every quote in
the file as it is now. A quote that no longer sits where it is cited is itself a finding.

**Quoting the worklist instead of the surface.** The worklist's claim column is a transcription.
Before ruling, open the surface and confirm the text still reads that way. If it does not, the
row is stale and the verdict is `cannot-determine — surface changed`, with the current text
quoted.
