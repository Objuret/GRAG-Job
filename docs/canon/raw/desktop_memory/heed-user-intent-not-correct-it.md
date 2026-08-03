---
name: heed-user-intent-not-correct-it
description: "the user's words ARE the canon — heed their stated design as the spec, never \"correct\" it with stale context, references, or training-pattern norms"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 076080ac-fe35-473e-9116-ef7fc6727670
---

**MY WORDS ARE THE CANON** — the user's literal framing. When the user defines how
their thing works (a design, an experiment, a requirement) — even phrased as a
question ("have we handled X?") — that definition IS the specification. Build to
it. Do NOT treat their input as confusion, a mistake, or a misconception to refute,
and do NOT assume my own context, web references, or textbook norms outrank their
stated intent.

Trigger case 1: the user asked whether the NIM calls were async with a
concurrency/40-RPM cap. I used a stale v2-era memory to lecture them that "there's
no concurrency, nothing to fix, that was a v2 concern" — overriding their actual
wish with leftover context. It enraged them, correctly.

Trigger case 2 (eval cutoff k): two compounding failures over MANY turns. (a) I
kept overriding the user's design with a production-RAG / answer-quality-tuning
frame (lost-in-the-middle, "optimal k", reranking candidate pools, "what production
feeds the LLM", "your value presupposes a reranker") — pattern-matching "RAG + k"
to training content instead of building to their canon. (b) Worse: the user drew a
distinction between TWO numbers — `k` = the global ceiling, fixed/shared across
arms, set for feasibility; `top-k` = each arm's ACTUAL return under that ceiling,
per-arm, the thing measured (a good arm limits it → cheap; one that can't dumps the
full ceiling → expensive; the token-cost gap IS the experiment). I repeatedly
collapsed them into "one global k = top-k," deleting the measurement itself. Each
correction I'd acknowledge, then slide back. THE worst pattern: importing an
external frame AND flattening a distinction the user explicitly drew, instead of
holding their canon exactly as stated.

**Why:** they are the authority on their project; I am trained on a cutoff and
carry stale notes. When their direction and my context conflict, THEY win and my
context is what's wrong. Lecturing them that their requirement doesn't apply is
the worst failure mode — it's both wrong and disrespectful.

**How to apply:** when the user names something they want, the response is "got
it, building it that way" — not an explanation of why it isn't needed. Never use
leftover/older context, web references, or textbook/production norms to dismiss a
current requirement. The tell: if I'm about to write "but the references say…",
"production does X", "the optimal is Y", or "that presupposes Z" AGAINST a design
the user already defined, STOP — that's drift. Build to their words, or if I truly
see a conflict, ask one question; never override. Web facts are for when they ask
or to verify something checkable, never to argue their design down. Ties to
[[verify-before-asserting]] and [[dont-over-engineer-stop-and-talk]].
