# Completed ordering, description-gating and feedback comparison

All 95 original cases completed. Independent verification passed for 34,295
deliveries (361 programs), input seals, source-ID metrics and 72k boundary
accounting. There are 242 distinct full-population order signatures. The canonical
reference and the prior mean-query leader both reproduce their earlier full-order
hashes and deliveries exactly on all 95 cases.

Evidence directory: `output/research/2026-09-23-ordering-programs-v2/`.
It contains `independent-verification.json`, `parent-reproduction-check.json`,
`structural-findings.json` and the two exported fixed-program files below.

## Different leaders for different population summaries

| Fixed program | Total gold-source hits | Macro per-question recall |
| --- | ---: | ---: |
| Previous best, reproduced as `ordering_0210` | 1,890 | 51.6586% |
| `ordering_0273`, highest total hits | 1,945 | 52.5244% |
| `ordering_0016`, highest macro recall | 1,939 | 53.2329% |

The hit leader gains 55 source links over the previous best, with 14 case wins,
13 losses and 68 ties. It is a development-selected fixed rule, not a per-question
gold-selected choice. Each question has its own 72,000-character serving budget.
These source-ID results are not RAGAS and do not establish unseen-query performance.

## What the highest-hit construction does

`best-by-gold-hits.json` exports the complete executable `ordering_0273` program.
It combines tag and chunk-description matches by maximum, applies per-query facet
readings, and averages query evidence **before** strongest-tag aggregation onto
chunks. Facets stay separate. It performs four steps over shared channel groups,
with maximum sponsor aggregation, half attenuation and the reduced destination
query-description gate at each step. Only the latest step feeds the next;
original seeds are not reinserted during the walk.

Direct and resulting graph evidence join by minimum. Whole-question description
similarity multiplies the resulting facet streams, which recruit independently
in shared-visited complete-tier batches. Saved scope is admitted first, with
linked-record recovery afterward. Stable ID resolves remaining nomination ties.

The macro leader uses product matching, combines query evidence **after**
strongest-tag aggregation but **before** graph traversal, traverses twice, and
uses joint recruitment. Other settings are in `best-by-macro-recall.json`.

## Matched effects in the hit-leading context

| Single change toward the leader | Total-hit change | Wins / losses / ties |
| --- | ---: | --- |
| One traversal step to four | +88 | 21 / 12 / 62 |
| Two traversal steps to four | +38 | 13 / 8 / 74 |
| Joint to independent facet recruitment | +47 | 7 / 2 / 86 |
| Description gate after walk to gate at every step | +105 | 23 / 14 / 58 |
| Reinsert original seeds to latest-step-only feedback | +88 | 21 / 12 / 62 |
| Query reduction after traversal to before tag aggregation | +6 | 12 / 15 / 68 |

The last change improves aggregate hits while reducing macro recall by 0.4106
percentage points. There is no single ordering that dominates every metric or
every question. The facet-recruitment comparison uses automatic nomination:
changing recruitment also changes the scheduler from joint rank to independent
batches, as explicitly defined by the construction.

## Remaining work

The combined-neighbor and structural-scope populations are still running. Their
completed results must be compared and combined with these ordering choices.
The hit leader lies at the largest tested depth (four), so deeper and odd-length
walks require a follow-up before interpreting four as a preferred stopping point.
This finite catalog does not establish convergence, optimal stopping, a global
optimum or completion of the broad structural objective. Preserve both leaders
and the matched tradeoffs rather than selecting a per-case oracle at runtime.
