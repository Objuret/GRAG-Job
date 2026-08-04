# New-session starter

Paste this into a fresh session.

---

Read `docs/canon/CONTRADICTION_MAP.md`. That is the work. Everything else in
`docs/canon/` is reference — open it only when a specific claim is in dispute.

Three separate things, and you keep them apart. **Intent** — what was supposed to be
built — exists only in my own typed turns, `docs/canon/raw/user_turns_all.md`. **State** —
what actually exists — is the git history itself: commits, diffs, the file contents at
each commit, plus the code and the run outputs. **Interpretation** — every document,
memory file, state doc and agent definition here, the `docs/canon/` docs included — is
some agent's claim about intent or state, unreviewed, holding only as far as its citations.

State is evidence of drift from intent, never justification for it. "It is in the code"
and "the commit says so" are not arguments to me — they are the thing I am questioning.

Don't assert what I wanted without quoting the turn and its line. No record means say so
and call it your proposal. Where the map says a fix needs my ruling, ask me — one question,
when the work actually reaches it. Don't rewrite files, mark anything settled, or touch
`v3/` code without me saying so.

The layers, so nothing gets filed wrong: the **v3 harness** is where we work; the **modified
v1 artefact** (`v3/pipelines/artefact_v1.py`, `artefact_v1_det.py`) is the system under test;
the **herb-eval graph** is v1's baked build — content stripped and re-embedded, never
retagged, so anything wrong in it needs a retag, not a code change; `v3/artefact/` is the
native rebuild, not adopted.

Short answers, plain English. Branch is `user-canon-record`. Don't write memory files.
