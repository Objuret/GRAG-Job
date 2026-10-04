# One fixed area-admission intervention

Written before observing the intervention outputs. This tests a construction
decision, not another coefficient search. All cases are reused and exploratory.

## Motivation and policy

The recorded query-side design says that literal names land on actual graph
nodes, graph routes identify areas, and tags/descriptions rank inside those
areas first while outside candidates remain available. The current arm instead
merges a global rank and an area-relative rank at equal depth. Area rank 1 and
global rank 1 receive the same admission priority irrespective of score gaps.

The single alternative is **area first**: positive in-area nominations ordered
by the unchanged joint scores precede positive outside nominations ordered by
the same scores. Keep ties. With no resolved area, use the same global order.
Apply identical record recovery after nomination and the same sponsor-first
within-frontier ordering in both policies. Outside candidates are retained;
with a finite budget, they may receive no context when the area fills it. This
is strict ordinal scope priority, not a numerical soft boost or a claim that
membership proves relevance.

It is an explicit candidate interpretation, not a declaration that the historical
wording settles every question. In particular, misresolved or overly broad areas
can make it worse. Do not silently promote the candidate to the serving default.

## Fixed comparison

Use all 85 successful saved records from the remaining-90 run. Keep its five
interpreter failures visible in failure-inclusive recall. Do not retry them.
Use each record's saved literal structural area, not the benchmark product ID
and not a new interpretation. This isolates scheduling; the later broader
structural resolver is not under test here.

Four conditions, fixed now:

1. Equal-depth scope, original joint score.
2. Equal-depth scope, topic contribution only.
3. Area-first scope, original joint score.
4. Area-first scope, topic contribution only.

Both joint conditions use coefficients (1, .25, .25, .25, .25). Topic-only uses
the saved independent topic contribution. No new embedding, querytagger, facet
measurement, graph propagation, answer generation or LLM judging. The controls
identify whether an area-policy effect depends on the existing auxiliary
contribution; they do not estimate optimal weights.

Archived original delivery is separately reconstructed as an integrity check.
The sponsor-first repair is common to all four conditions; its effect relative
to the archived order is reported separately to avoid attributing it to scope.

## Measurement and integrity

- Freeze source/input hashes before running. Stream private records; export only
  allowed IDs, counts, ranks/positions and numeric summaries.
- Use the verified chunk-to-artifact mapping and actual serialized unit lengths.
  Apply the existing 72,000-character prefix/partial-boundary contract. Partial
  boundary units receive no new artifact-ID credit.
- Reconstruct archived budget and credited-ID set exactly on every saved case.
- Finish all four deliveries for a case before joining its gold IDs.
- Execute the installed RAGAS ID precision/recall metric classes, checking their
  results against set intersections. Report paired means, wins/losses/ties,
  aggregate source-link counts, failure-inclusive recall and area availability.
- Report the joint-minus-topic effect under each scope policy, and scope-first
  minus equal-depth under each score policy. Do not select a winner from a sweep.
- Keep a source-ID movement record. Gold does not influence construction.

These are citation-ID measures, not exhaustive semantic relevance or answer
quality. A large scheduling effect would identify an important construction
choice; a small/null effect would reject this particular priority hypothesis as
a large practical improvement. Neither validates the facet measurements alone.
