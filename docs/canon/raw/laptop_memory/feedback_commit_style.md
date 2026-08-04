---
name: Commit message style (thesis repo)
description: How to write git commit messages in this repo — no AI attribution, short and human
type: feedback
originSessionId: edcc9e88-3eae-45d0-a17f-817ef32c0ac6
---
Commit messages in this repo must be clean, short, and human-written in style. Do NOT include the `Co-Authored-By: Claude ...` trailer, the "🤖 Generated with Claude Code" footer, or verbose multi-paragraph AI-generated bodies.

**Why:** This is the user's exjobb (master's thesis) project. They do not want AI attribution or generated boilerplate in the git history — it reflects on their academic work.

**How to apply:** When committing in this repo, write a concise message (ideally a single subject line, optional 1–2 short body lines only if genuinely needed). Omit all AI/Claude attribution trailers and "generated with" footers, even though global tooling defaults suggest adding them. Propose the message and let the user adjust before committing if the change is non-trivial.
