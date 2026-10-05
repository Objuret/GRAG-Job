"""One querytagger call; the query's tags, description and question order the whole pool.

Every step is a construction of this arm unless the docstring names his sentence.

Interpretation: ONE querytagger call (`query_content`; his 2026-09-26 "dont do 3 different
calls"): the question in; the sought-content description and two tag lists out, each tag with
its five readings - the description-side tags, and the question-side tags written from the
question's own words (his 2026-09-29 "the tags the interpretor creates, perhaps it does some
from the query also? not just the description?"). strength, multikey, adjust_lower and walk read
both lists as query tags, each embedded beside the description; the other sorts read the
description-side list only. Two texts are matched against the chunk descriptions: the question
itself and the description (his 2026-09-25 "the same but from the prompt"). HERB_V4_OFFLINE=on
reads the querytagger answer from the cache only: a question without a good cached answer raises
before any model call. off (the default): a miss asks the model, and a cached failure is asked
again once.

HERB_V4_SORT=strength (the 2026-10-04 build, chosen by name; the default from 2026-10-04 to
2026-10-05). One strength per chunk from the tags, the description and
the structure; the whole order goes to the harness, nothing is cut. The arithmetic is
`v4_strength.strength_order`. N is the eligible graph tags - every graph tag except those whose
name equals a product name casefolded - and E the edges whose tag is eligible. Every value is
read in one unit, his 2026-10-04 "well, you have to be aware of the different scales of values
between each thing": its standing in its own population, (value - median) / (1.4826 * the
median absolute deviation from the median); the spread unit is the orchestrator's. Each link,
his sentence or the orchestrator's:

  1. Closeness: his 2026-10-04 "if we order the tags accordingly, closeness by embedding is the
     first order, then somehow we weightadjust them based on the facets? this gives us a
     chunk-pool, correct?". Per query tag q of either list, fit(q, t) is the standing of
     cos(q, t) over the N eligible graph tags. A zero spread raises.
  2. The edge's five values, query-independent: his 2026-09-29 "topic is also a fucking facet
     value..". topic(e) is the standing of cos(tag, chunk description) over E. Each of temporal,
     why, activity, concreteness is the normal score of the edge's average rank in its column
     over E, the standard normal quantile of (rank - 1/2) / |E|, ties sharing a rank; the
     columns are the values multikey reads, and only their order is used. The rank-to-normal
     step is the orchestrator's.
  3. The query tag's five readings weigh the edge's five values:
        w(q, e) = sum over the five of share_f(q) * value_f(e)
     share_f(q) q's reading over the sum of q's five readings; five equal shares when that sum
     is 0. The weighted mean is the orchestrator's.
  4. The tag route: s(q, c) = max over c's eligible edges e = (t, c) of fit(q, t) + w(q, e); a
     chunk with no eligible edge has no s. The plus is the orchestrator's.
  5. The query tags are not equal and are not added up: his 2026-09-10 "a chunk beeing supported
     by more parts, does not mean it's a better fit, thats different scales or things to
     measure". centrality(q) = cos(q, the query description), both vectors from the one
     query-role embedding call that embeds q (`_query_cosines_and_centrality`), a negative one
     as 0, over the question's largest; no positive cosine raises.
        T(c) = max over q of centrality(q) * max(s(q, c), 0)
     and 0 for a chunk with no eligible edge. The relative centrality and the positive part are
     the orchestrator's.
  6. Tags and description: his 2026-08-11 "the chunk descriptions and the tags are supposed to
     work TOGETHER to find gold.. it's a combo..". D(c) is the standing of cos(query
     description, chunk description) over the chunks, Q(c) the same for the raw question;
        S(c) = T(c) + max(D(c), Q(c))
     max(D, Q) and the plus are the orchestrator's.
  7. Structure, strengthening only: his 2026-09-14 "That's the point, letting the graph
     structure tell which area the information can be found". For each node type - product,
     channel, file (the chunk's relpath) - and each chunk c with another chunk under the same
     node,
        boost(c) = max(0, mean of S over the other chunks under the node
                          - mean of S over all chunks)
     a chunk under several channels takes its largest channel boost; S'(c) = S(c) + the three
     boosts. Nothing is lowered and no chunk is removed. The whole form is the orchestrator's.
  8. Near-equal is equal, the orchestrator's: level(c) = floor((max S' - S'(c)) / step), step =
     COS_NOISE over the median of the question's query tags' fit spreads. Order: level; inside
     a level the four facet normal scores of the chunk's winning edge, descending, in the order
     of the winning query tag's readings for temporal, why, activity, concreteness, largest
     first, equal readings in that order; then chunk id.
  This arm's: an exact tie between two edges of a chunk goes to the earlier edge, between two
  query tags to the earlier query tag in the list; D where D = Q; inside a level a chunk with no
  eligible edge follows the chunks that have a winning edge; a chunk counts once under a node.

HERB_V4_SORT=multikey (chosen by name; the default from 2026-10-05 morning to that evening). His 2026-09-05 "i had a quick and easy thought, that the
queryfacets is the order of sorting-prio based on facets for tags, so, if facet 1 is most
important for a tag from query, that is sorting order 1, and descending meaning that they are
"sorted".. bah.. like.. multi-key sort or multi-level sorting."; 2026-09-06 "yeah, so, first
you pick a fizzy value for fit of tags via the tag vs querytags embeddings, right? thats how
you PICK the tags, when the tags are picked, how do we decide which matters for this query?";
2026-09-06 "perhaps we should have the order slightly fuzzy, meaning for a specific order,
things can be called "equal" if within a certain range of eachother"; and 2026-09-30 "build
that" (not in the canon file) to the order fit -> the four facets in the query tag's order ->
topic and the description -> chunk id. The sort is `v4_multikey.multikey_order`.

  Units: every edge (q, t, c), q a query tag of either list, t every graph tag except those
  whose name equals a product name casefolded, c every chunk on t's HAS_TAG edge (the pool
  holds only chunks with a product edge). No pick, no cut: every such edge is sorted. Each
  edge's key, compared part by part, the smaller first:
  1. fit: floor((best cos(q, t) over every edge of the question - cos(q, t)) / W). The anchor
     is the question's one best, not each query tag's own, so a query tag whose nearest graph
     tag fits badly lands deep (his 2026-09-25 "auto-lower because of bad fit"); the one anchor
     is the orchestrator's. W is HERB_V4_FITEQ, one of the two widths this arm names in
     BANDS: noise (COS_NOISE, 0.002) or paraphrase (0.028). Neither width is his ruling; both
     are kept, noise is the default.
  2. the four facets temporal, why, activity, concreteness - topic not among them (his
     2026-09-29 "i dont think topic can be bart of that", relayed to this arm, not in the
     canon file) - in the order of q's own readings for those four, largest first; equal
     readings keep the order temporal, why, activity, concreteness (the orchestrator's). Per
     facet the edge's value, the higher the more, levelled floor((best value of that column
     over the question's edges - value) / gap). The value is the edge's mean round-1 head score
     over the 24 bootstrap refits (`bootstrap/scores_b24.npz`), the quantity the gap was
     measured on; the gap is the column's own retrain flip gap on uniform edge pairs, "gap
     (any)" in `bootstrap/BANDS.md`'s per-column table, since inside a fit level the key
     compares edges of different chunks and tags (both the orchestrator's reading of "equal"
     for a facet). Two edges of different query tags meet in one facet slot on the facet each
     one's own query tag put there.
  3. topic: floor((best cos(t, chunk description) over the question's edges - cosine) /
     COS_NOISE).
  4. the description, then the question: floor((best cosine over the chunks - cosine) /
     COS_NOISE) for cos(query description, chunk description), then for cos(raw question,
     chunk description). Topic -> description -> question is the orchestrator's order inside
     his 2026-09-29 "didnt we decide that desc and topic are "the same shit" more or less?"
     (not in the canon file).
  5. chunk id.
  The graph structure enters as two keys per chunk, his 2026-09-30 "how about testing all
  components together instead, like, you know.. the actual artefact..?" (not in the canon
  file); the keys and both places are the orchestrator's:
  - landed: 0 if the chunk sits in the question's landed area, else 1. The names in the raw
    question land on structure nodes and the area is the meet of the distinct landings
    (`landing.land`, `areas`, `combine`, as `_area_rank` reads them; his 2026-09-14 "a name
    and OR a product or whatever, should still be a 'limited area'. the combination i
    mean"; and "That's the point, letting the graph structure tell which area the information
    can be found"); a single landing is its own area; no landing gives every chunk 0. A key,
    never a cut. Two rules of the orchestrator's: a capitalised question word the corpus
    carries (the pool chunks' texts, casefolded) is a word, not a misspelling, and never
    reaches landing's nearest-name pass; a landing whose nodes reach no chunk defines no area
    and is dropped from the meet, recorded in meta.area.dropped.
  - seed: the chunk's distance to the seeds, the chunks an edge at fit level 0 reaches: 0 a
    seed, 1 sharing a [:channel] node with a seed or file-adjacent to one, 2 under the same
    product as a seed, 3 otherwise. File adjacency is artefact_v3's `file_adjacency` (parts
    of one record whose ranges overlap or touch; consecutive messages of one channel;
    overlapping index runs), the channels and products are read by artefact_v3's
    `load_shape`.
  HERB_V4_STRUCT_AT=after_facets (the default) puts the two after the four facets, "later in
  the line" (his 2026-09-29 "i think this is better used later in the line, if at all", not
  in the canon file); after_fit puts them right after fit; off leaves both out, the control.
  A chunk takes the place of its best edge, its first appearance in the sorted edge list (the
  orchestrator's reading of the tags carrying their chunks). Chunks no eligible edge reaches
  follow every reached chunk, by their own keys in the same order (the orchestrator's).

HERB_V4_SORT=adjust_lower. Each link, his sentence or the orchestrator's:

  1. The pick is the fit, as a weight, with no cut: his 2026-09-06 "first you pick a fizzy
     value for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the
     tags", and "auto-lower because of bad fit" (2026-09-25, relayed to this arm, not yet in
     the canon file). Every query tag q reaches every graph tag t except those whose name
     equals a product name, casefolded (the 2026-09-14 querytagger description he confirmed,
     "Seems fine.", keeps names of products out of the tags as structure; applied to the
     graph side by the orchestrator). The fit enters as it is, negative included: a bad fit
     lowers the edge by its own size, nothing is dropped. A chunk no eligible edge reaches
     sorts after every reached chunk, whatever the reached chunks' scores.
  2. Topic is the edge's weight, the four facets adjust it: his 2026-09-18 "my thinking is that
     the "main weight" on a tag, is the topic one, and the others adjust that weight depending
     on the relevance of a facet to the query"; the four stored columns as ranks, his
     2026-09-20 "ok, i am ready to use ranking instead of actual weights, one can convert
     ranks to weights". Per edge
        rel(q, t, c) = fit(q, t) * T(t, c) * prod_f pct_f(t, c) ** (q_f / sum_f q_f)
     over temporal, why, activity, concreteness; q_f the querytagger's reading; pct_f the
     stored percentile rank r/n over all 61,018 edges (in [1/n, 1], never 0). The facet factor
     is the weighted geometric mean of the edge's four percentiles, so it lies between the
     edge's lowest and highest percentile and never collapses the scale; it is 1 when
     sum_f q_f = 0 and under HERB_V4_FACETS=off. The product-of-powers form is the
     orchestrator's (given to this arm 2026-09-28), the normalisation by sum_f q_f the
     orchestrator's, the percentile convention r/n the orchestrator's. T is the topic cosine
     as it is. Where the query tag's topic reading enters is not ruled: HERB_V4_QTOPIC=off
     (default) leaves T = topic; exp sets T = max(topic, 0) ** q_topic where q_topic > 0 -
     the clip at 0 only there, a fractional power of a negative number being undefined - and
     leaves T = topic where q_topic = 0.
  3. Combination over edges, the orchestrator's choice: HERB_V4_EDGECOMB=sum (default) adds
     every (q, t) reaching c; max takes per query tag the best graph tag and sums over query
     tags; best takes the chunk's single largest (q, t) term over every query tag of both
     lists and every graph tag reaching it, nothing added to it. Measured 2026-09-10:
     documents carry 18.5 tags a chunk against 12.8 for Slack, so sum lifts documents by
     their tag count. sum and max stand against his 2026-09-10 "a chunk beeing supported by
     more parts, does not mean it's a better fit". Negative terms and reached chunks with a
     negative score are counted in the diagnostics.
  4. The description and the question, his 2026-09-25 "the same but from the prompt" and
     2026-09-02 "the combo of query facets vs tagfacets, query tags vs tags and then query
     desc vs chunk desc"; the tags lead, his 2026-09-26 "tags are the main path, not
     chunk_desc" (relayed, not yet in the canon file). HERB_V4_DESCJOIN=key (default): the
     tag score sorts continuously, descending; on an exact tie cos(description, chunk desc),
     then cos(question, chunk desc), each levelled at COS_NOISE (0.002, the embedder's
     measured resolution on a cosine) below its best. mul: the tag score times
     max(cos(description), 0) times max(cos(question), 0), continuous. The description
     before the question is the orchestrator's.
  5. Landing: his 2026-09-14 "That's the point, letting the graph structure tell which area
     the information can be found" and "a name and OR a product or whatever, should still be
     a 'limited area'. the combination i mean": on an exact tie of everything before it, a
     chunk in the meet of the question's landings (`landing.combine`) sorts first. A key,
     never a cut. Then chunk id.

HERB_V4_SORT=multirank. His 2026-09-05 "the queryfacets is the order of sorting-prio based on
facets for tags ... like.. multi-key sort or multi-level sorting" and 2026-09-06 "things can be
called "equal" if within a certain range of eachother"; his 2026-09-20 "both" to the two
readings (the multi-key sort and the adjust):

  1. Per chunk its best (q, t) edge by strength = fit * topic, both as they are, over the same
     casefolded non-product tags (the orchestrator's choice of best).
  2. Key: the level of that same strength, floor((best strength of the question - strength) /
     COS_NOISE), outermost - one quantity chooses the edge and keys it; COS_NOISE as the step
     on a product of two cosines is the orchestrator's. Then the edge's five levels in the
     order of that query tag's five readings, largest first (equal readings keep the facet
     order topic, temporal, why, activity, concreteness - the orchestrator's). A facet level
     is floor((column max - stored score) / gap) over all edges, gap the pooled same-chunk
     retrain flip gap read from `rounds/round1/bootstrap/BANDS.md` (1.00 score units; SPEC-v2
     of 2026-09-21); its share of edges per level, the conversion to percentile, is in the
     provenance. Topic's level is floor((max cosine - cosine) / COS_NOISE) over all edges -
     COS_NOISE as topic's "equal" is the orchestrator's (SPEC-v2 also names 0.028, the
     description write noise).
  3. Then the description level, the question level, landing, chunk id. Chunks with no
     eligible edge follow every reached chunk, by description level, question level,
     landing, id.

HERB_V4_SORT=concept (kept for the record; the 2026-09-27 build). Each piece, his or this arm's:

  1. The fit is the pick, as a weight, with no cut: his 2026-09-06 "first you pick a fizzy
     value for fit of tags via the tag vs querytags embeddings, right? thats how you PICK the
     tags". Every query tag q reaches every eligible graph tag t with fit(q, t) = cos(q, t).
     Eligible is every graph tag except the product-name tags: the querytagger description he
     confirmed on 2026-09-14 ("Seems fine.") keeps "names of people, products or channels" out
     of the tags as structure, and this arm applies the same to the graph side. The
     product-name exclusion is on under concept whatever HERB_V4_TAGSIDE says. The metadata
     chunks are already out: the pool holds only chunks with a product edge, and prepare
     asserts every graph tag has an edge into that pool.
  2. Topic is the edge's weight and the four other facets adjust it: his 2026-09-18 "my
     thinking is that the "main weight" on a tag, is the topic one, and the others adjust that
     weight depending on the relevance of a facet to the query". Per edge
        rel(q, t, c) = fit+(q, t) * topic+(t, c) * (1 + adjust(q, t, c))
        adjust(q, t, c) = (1/4) * sum over temporal, why, activity, concreteness of r_f(q) v_f(t, c)
     with topic(t, c) the plain cosine of the tag vector to the chunk description vector,
     v_f the stored round-1 `_pos` columns, r_f the querytagger's readings for those four
     facets (its topic reading is not used). The size of the readings is kept - no division
     by their sum - so readings of 0.1 give a small adjust and readings of 1.0 the plain mean
     of the four positions; (1 + adjust) spans [1, 2]. adjust is 0 under HERB_V4_FACETS=off.
     x+ is max(x, 0): a negative closeness is no closeness, so a negative fit times a
     negative topic cannot turn positive. The mean over four, keeping the reading's size,
     and the clipping are this arm's constructions.
     Per query tag, a chunk's tag term T_q(c) is the max of rel over its edges - the best edge
     by the adjusted value, not by raw fit: his 2026-07-31 "perhaps the query-adjustment comes
     first before what the best fit is for this query", and the v1/v2 construction "a chunk
     keeps its best tag within a part". The tag score S(c) = sum_q T_q(c) is the v1/v2 "sums
     across parts": a sum of strengths, which stands against his 2026-09-10 "a chunk beeing
     supported by more parts, does not mean it's a better fit, thats different scales or
     things to measure". A chunk with no eligible edge has T_q = 0.
  3. The description adjusts the tag score the way the facets adjust topic:
        D(c) = cos+(question, chunk description) + cos+(description, chunk description)
     his 2026-09-25 "the same but from the prompt". HERB_V4_JOIN=adjust (default) scores
     S(c) * (1 + D(c)): the tag score sets the order and the description moves it by at most
     the factor (1 + D), D at most 2 in principle. This follows his 2026-09-26 "tags are the
     main path, not chunk_desc" and "topic and chunk_desc kinda triangulates", both relayed to
     this arm and not yet in the canon file. HERB_V4_JOIN=mul scores S(c) * D(c), symmetric:
     whichever factor has the wider relative spread leads. HERB_V4_JOIN=add scores S(c) + D(c):
     the tag/text balance is then set by how many tags the querytagger wrote (on the saved
     case, as relayed to this arm: 6 tags gave S median 0.19, 14 tags 0.56, against D about
     0.36). All three joins and the clipping of the text cosines are this arm's constructions.
  4. Order: score descending, then chunk id. Full order out; the harness cuts. No area key.

HERB_V4_SORT=chain (kept for the record; the 2026-09-26 stripped-back build), query -> tag -> chunk. His sentences it is built on:
2026-09-06 "first you pick a fizzy value for fit of tags via the tag vs querytags embeddings,
right? thats how you PICK the tags"; 2026-09-06 "perhaps we should have the order slightly
fuzzy, meaning for a specific order, things can be called "equal" if within a certain range
of eachother"; 2026-09-06 "you are sorting the fucking tags.."; 2026-09-02 "the combo of
query facets vs tagfacets, query tags vs tags and then query desc vs chunk desc"; 2026-09-13
"apparently we got it right with lucene and vector for tgose 72k caps, make sure the
artefact also follows that rule"; and "auto-lower because of bad fit", relayed to this arm
as his words of 2026-09-25, not yet in the canon file. Every number, grid, anchor and
join below is this arm's construction, not his:

  1. Fit levels, one scale for the whole question. best_fit_all is the highest fit of any
     query tag to any graph tag; every (q, t) pair gets
        level(q, t) = floor((best_fit_all - fit(q, t)) / COS_NOISE)
     over the whole graph, with no cut. A query tag whose nearest graph tag is a weak match
     therefore lands deeper than a strong query tag's best match. The grid (whole steps of
     COS_NOISE = 0.002, the embedder's measured resolution, the only constant), its anchor
     at the question's best fit, and a level number meaning the same thing for every query
     tag are this arm's constructions. Under HERB_V4_TAGSIDE=nonscope a product-named graph
     tag gets no level and best_fit_all is taken over the remaining tags.
  2. Facet relevance. His 2026-09-05 "the queryfacets is the order of sorting-prio based on
     facets for tags" and 2026-09-13 "we have the interpretor put a value on its tags in
     relation to the query... So we can weight-adjust the facets based on that":
        rel(q, t, c) = topic(t, c) * (1 + sum_f r_f(q) * v_f(t, c) / sum_f r_f(q))
     over the five facets, adjust 0 when sum_f r_f is 0 (and under HERB_V4_FACETS=off).
     topic(t, c) is the plain cosine of the tag vector to the chunk description vector; the
     v_f are the round-1 `_pos` columns of `output/facet_pairs/rounds/round1`, each uniform
     on [0,1] over all 61,018 edges as stored, never re-levelled per query, so (1 + adjust)
     spans exactly [1, 2]. The form of the adjustment is this arm's construction, not his.
     rel is levelled inside each fit level:
        rel_level = floor((max rel at that fit level - rel) / COS_NOISE)
     The anchor is the question's own pool: the highest rel among every query tag's edges
     at that fit level. It moves with the pool - another query tag reaching the same fit
     level with a stronger edge pushes every other edge there deeper. Applying COS_NOISE,
     the instrument's step on a cosine, to rel, a cosine scaled by a factor in [1, 2], and
     anchoring it at the pool's best are this arm's constructions.
  3. Description link. His 2026-09-02 "the combo of query facets vs tagfacets, query tags vs
     tags and then query desc vs chunk desc": d(c) = cos(the querytagger's description,
     chunk description), continuous, the tie-resolver after the tag keys.
  4. Chunk order. Every (q, t, c) edge carries the key (fit_level, rel_level); a chunk takes
     its BEST key over every (q, t) reaching it - no count, no sum. Reached chunks sort by
     (best key, -d(c), chunk id); chunks no query tag reaches follow, by (-d(c), chunk id).
     No text probe runs: neither the question nor the description is matched against chunk
     descriptions as a probe; the description enters only as d(c) after the tag keys. No area key.

HERB_V4_SORT=sum (kept for the record; the default on 2026-09-26, his "the same but from the prompt": the question text and
the description against the chunk descriptions, plus the tags): per query tag, the graph
tags within HERB_V4_BAND of its best fit are picked; per chunk the score is
    sum over picked (q, t) with an edge: fit(q, t) * topic(t, c) * (1 + adjust(q, t, c))
  + cos(question, chunk description) + cos(description, chunk description),
HERB_V4_PROBES selects the tag part, the text part or both, and HERB_V4_AREA=first sorts the
chunks of `landing.combine`'s meet first. The tag part and the text part are added one to
one with nothing making them commensurate: the topic factor measured mean 0.226, median
0.221, range 0.016-0.575 over 4,000 edges sampled from this layer (seed 0, 2026-09-26),
while a text probe hands every chunk a whole query-to-description cosine. Under a budget
the area boundary acts as a cut.

HERB_V4_SORT=walk (the 2026-10-05 build; the arm's default since that evening, on his "it's
time to also finish the build with the changes we discussed", with three knobs off the
walked-through PROPOSAL by default: HERB_V4_WALK_SHARES=off, HERB_V4_WALK_RANK=percent,
HERB_V4_WALK_STRUCT=trust1; the PROPOSAL is each knob's first value, `WALK_PROPOSAL`). The
chain `tools/walkthrough.py` prints step by step: one strength per chunk from the tags, the description and the structure;
the whole order goes to the harness, nothing is cut. The arithmetic is `v4_walk.chain`, the one
implementation the walk-through prints from and this arm sorts by. N is the eligible graph tags
- every graph tag except those whose name equals a product name casefolded - E the edges whose
tag is eligible, n the chunks. Every calculation below is the orchestrator's. M1 to M7 are
marked steps awaiting his word: this build settles none of them, each knob's default is the
step's PROPOSAL and each other value the alternative of the walk-through it names (A1 to A7,
`v4_walk.ALTERNATIVES`) or one of the two changes built after it (C3r, C4n,
`v4_walk.CHANGES`). A phrase standing in both tag lists is two query tags: it enters
twice, once with each list's readings.

The embedder has two roles, and the graph's tag vectors and chunk description vectors are
stored in its passage role (`test/graph/reembed_herb_eval.py` embeds both under `passage`).
HERB_V4_WALK_TAGROLE sets the role the question's tags, both lists, are embedded in for their
cosines to the graph tags, the cos(q, t) of M1: passage (the default) or query. His 2026-10-05
"oh, fuck me, it's for, for example, the vector arm!" and "but duuuude.. OBVIOUSLY we should
use the similarity way, that was what i thought we were doing all the goddamn time!" (relayed
to this arm, not yet in the canon file): a tag against a tag is compared in the same role on
both sides; the query role is for a question against a text. Under query the tags are embedded
as every other sort embeds them. HERB_V4_WALK_DESCROLE sets the role the query description is
embedded in for its cosines to the chunk descriptions, the D of M5, and HERB_V4_WALK_QUESTROLE
the role of the raw question for its cosines to the chunk descriptions, the Qs of M5: passage
or query. The description defaults to passage on his 2026-10-05 "great, so now everything has
been embedded in the same way? i mean litterally everything that has been embedded for the
artefact should use this, not only the tags" (relayed to this arm, not yet in the canon file);
the raw question defaulted to passage on the same sentence for that evening and defaults to
query since his "yes to the question" the same night, to the orchestrator's "put the raw
question back in question mode. It is the one text that actually is a question, and that
mode exists for a question against a text" (10smoke 0.502 against 0.449). The centrality of M4
compares a tag with the query description in one role for both, the passage role when the
tags' and the description's knobs both say passage and the query role in every other
combination - the orchestrator's rule, unruled. Under the defaults the tags, the description
and the centrality are in the passage role and the raw question in the query role, and each
text is embedded once per call, the description beside each tag list (a
repeat is read from the rows kept on the side); under HERB_V4_WALK_TAGROLE=passage with
HERB_V4_WALK_DESCROLE=query the tags are embedded twice, alone in the passage role for the
graph tags and beside the description in the query role for the centrality; under query with
passage the description is embedded twice (`_walk_cosines`). All three at query reproduce the
17 runs of 2026-10-05 08:28Z-09:51Z.

Each link, with his sentence where this file quotes one for it:

  M1. Closeness into a weight: his 2026-10-04 "if we order the tags accordingly, closeness by
      embedding is the first order, then somehow we weightadjust them based on the facets? this
      gives us a chunk-pool, correct?" and "well, you have to be aware of the different scales
      of values between each thing". Per query tag q of either list, z_q(t) is the standing of
      cos(q, t) over the N eligible graph tags, (cos - median) / (1.4826 * the median absolute
      deviation from the median), and fit_q(t) = max(z_q(t), 0). A zero spread raises.
      HERB_V4_WALK_FIT=standing (the default); raw (A1): fit_q(t) = cos(q, t). Under raw more
      than the fit is exchanged: the tag term T is in raw cosines while the text side (M5)
      stays in standings, the lifts (M6) are taken on the sum of the two, and the level step
      (M7) stays COS_NOISE over the median s_q.
  M2. The edge's five values on one scale, query-independent: his 2026-09-29 "topic is also a
      fucking facet value..". His 2026-09-20 "ok, i am ready to use ranking instead of actual
      weights, one can convert ranks to weights" stands in this file for the four stored
      columns as ranks; ranking topic, a cosine, the same way is the orchestrator's. For each
      of topic = cos(tag, chunk description), temporal, why, activity, concreteness - the four
      are the values multikey reads - pos_k(e) is the edge's average rank in the column over E,
      1 the smallest, ties sharing a rank, over |E|. The walk-through prints no alternative to
      it; no knob.
  M3. The query tag's five readings meet the edge's five values: his 2026-09-13 "we have the
      interpretor put a value on its tags in relation to the query... So we can weight-adjust
      the facets based on that".
         share_q = q's five readings over their sum, five equal shares when that sum is 0
         R_q(e) = sum over the five of share_q[k] * pos_k(e)
         w_q(e) = fit_q(t) * R_q(e) / 0.5
      0.5 stands for the middle position. Exactly, an edge at the middle rank of all five
      columns has R = (|E| + 1) / (2 |E|) and the factor R / 0.5 = (|E| + 1) / |E|, not 1. For a
      positive fit an edge whose factor is above 1 raises the closeness and one whose factor is
      below 1 lowers it; a fit of 0 stays 0; under HERB_V4_WALK_FIT=raw a graph tag with a
      negative cosine turns it round, the higher edge taking the lower w.
      HERB_V4_WALK_SHARES=readings (the PROPOSAL); equal (A3): five equal shares; off (A3b, the
      arm's default since 2026-10-05 evening, his "well, multiplying it might not really
      actually represent their relationship tho"):
      w_q(e) = fit_q(t). Under equal and under off the readings still give the facet order of
      M7; under off the edge's positions leave the weight, and inside a level the order is
      still the winning edge's four facet positions.
      HERB_V4_WALK_RANK=off (the PROPOSAL); same (C3s, the arm's default since 2026-10-05
      late night, on his "what matters is the fucking semantic relevance of that number for
      the tag"): the picked graph tags of a query tag are those scoring at least what the
      graph's own same-thing pairs score - tags equal once lower-cased or once a final s is
      dropped; the level is the point 5% of those pairs' cosines lie under, measured at
      prepare from the stored vectors (`v4_walk.same_thing_level`, 0.92 on this graph) - and
      only their edges are ranked by the four facets as described below and placed between
      that level and the closest tag; a query tag with no graph tag at that level is left as
      it is. The pairs, the 5% point and the placement are the orchestrator's. percent (C3p,
      the default for an hour before it): the ranking with the class a share of the closest tag's own
      score - class 0 is every graph tag scoring at least 95% of the closest one - on his
      "on the stopgap, why not just use a relative %?"; 95% is the share NVIDIA's hard-negative
      recipe for this embedder calls "so close to the positive they may actually be relevant",
      its transfer from passages to tags the orchestrator's (`v4_walk.EQUAL_SHARE`); any tag
      role. picked (C3r, the default for an hour that evening; built 2026-10-05 after the
      walk-through on his "perhaps we just use them as ranking (the 4, not topic) based on
      the most important in order from the query, per tag?" and "rank the TAGS, no, i am not
      supersure how we we that"; the form, the class and its width are the orchestrator's):
      per query tag the graph tags stand in classes one self-difference
      wide below its closest tag - the self-difference is how far a graph tag's own name,
      embedded in the passage role, lands from its own stored vector, the largest over 100
      seeded eligible graph tags, measured once at the first question that needs it, before
      that question's clock starts (`_walk_width`); inside a class the
      edges are ordered by the four facets in the query tag's facet order, each facet in
      classes of its retrain gap, then topic, then the cosine; an edge's cosine becomes its
      class's upper edge minus the self-difference times its place over the class's size, and
      its fit the standing of that. It needs HERB_V4_WALK_TAGROLE=passage and is refused
      with HERB_V4_WALK_TAGS=peredge. With HERB_V4_WALK_SHARES=off the four facets leave the
      weight and act through that ranking and through the order inside a level (M7); topic
      as the key after them is the orchestrator's, his sentence says "the 4, not topic".
      Reviewed 2026-10-05: the self-difference is the gap between the serving that built the
      stored tag vectors and the local one (docs/ENVIRONMENT.md), the largest of 100 probes
      and set by one name, one width for every query tag - not his "fully relative to that
      facets tags numberrange" - and an edge's placed cosine also depends on how many edges
      share its class.
  M4. What a chunk takes from its tags, and the query tags: his 2026-09-10 "a chunk beeing
      supported by more parts, does not mean it's a better fit, thats different scales or things
      to measure". v_q(c) is the largest w_q over c's eligible edges, 0 with none, with no
      correction for n_c, the number of c's eligible edges. HERB_V4_WALK_TAGS=best (the
      default); pooled (A4a): in place of v the k-th largest w_q over E, k = ceil(p * |E|),
      p = 1 - (1 - K / |E|)^n_c, K the eligible edges with w_q >= v_q(c); peredge (A4e): in
      place of v the k-th largest fit_q over N, k = ceil(p * |N|), p = 1 - the product over c's
      edges i of (1 - K_i / |N|), K_i the eligible graph tags t with fit_q(t) * R_q(i) / 0.5 >=
      v_q(c); sum (A4b): in place of v the sum of w_q over c's edges; off (C4n, added
      2026-10-05 to measure the text and the structure without the tags): v = 0 for every
      chunk.
      centrality_q = cos(q, the query description), both vectors from the one embedding call
      that embeds q beside the description, in the centrality's role
      (`_query_cosines_and_centrality`), a negative one as 0, over the question's largest; no
      positive cosine raises.
         T(c) = max over q of centrality_q * v_q(c)
      HERB_V4_WALK_QTAGS=central (the default); equal (A4c): centrality 1; sum (A4d): the sum
      over q in place of the max.
      The two sums stand against that sentence of his: HERB_V4_WALK_TAGS=sum adds up a chunk's
      edges and HERB_V4_WALK_QTAGS=sum its query tags, so the tag term grows with the chunk's
      number of eligible edges, or with the number of query tags (a phrase in both lists
      counted twice), while the text side and the level step stay as they are. Both are kept as
      alternatives the walk-through measured, not as readings of the sentence.
  M5. The description joins: his 2026-08-11 "the chunk descriptions and the tags are supposed to
      work TOGETHER to find gold.. it's a combo.." and 2026-09-25 "the same but from the prompt".
      D(c) is the standing of cos(query description, chunk description) over the chunks, Qs(c)
      the same for the raw question, neither clipped;
         S(c) = T(c) + max(D(c), Qs(c))
      HERB_V4_WALK_TEXT=better (the default); off (A5a): S = T; description (A5b): S = T + D;
      clipped (A5c): S = T + max(D, Qs, 0).
  M6. Structure, strengthening only: his 2026-09-14 "That's the point, letting the graph
      structure tell which area the information can be found". Two groupings: the product; the
      near group, a connected component of the file adjacency (artefact_v3's `file_adjacency`)
      with at least two chunks. Product: x = S, against the mean of S over the chunks. Near:
      x = S - the mean of S over the chunk's product, against the mean of x over the chunks of
      the chunk's record kind that sit in a near group. For a chunk c in a group g of n_g
      chunks:
         raw(c, g) = the mean of x over g's members other than c - the reference of c
         trust(g) = tau2 / (tau2 + sigma2 / (n_g - 1))
         lift(c, g) = max(0, trust(g) * raw(c, g))
      sigma2 is the pooled within-group variance and tau2 = max(0, (SSB - (G - 1) * sigma2) /
      (M - the sum of n_g^2 / M)) the between-group variance, both on x less its reference;
      SSB the sum over the groups of n_g * (the group's mean - the mean over the
      memberships)^2, G the groups, M the memberships. S'(c) = S(c) + the two lifts. Nothing is
      lowered and no chunk is removed. HERB_V4_WALK_STRUCT=near (the PROPOSAL); trust1 (A6b)
      is the arm's default since 2026-10-05 evening, his "just as i dont think "amount of closely
      related chunks" makes a chunk more important"; off (A6a):
      S' = S; trust1 (A6b): trust 1; ref0 (A6c): the near group against 0; double (A6d): three
      groupings, product, channel and record (the near group), channel and record on x against
      0, a chunk in several channels taking its largest lift,
      tau2 = max(0, SSB / M - G * sigma2 / M), S' = S + the three lifts.
  M7. Near-equal is equal, and what breaks a tie: his 2026-09-06 "perhaps we should have the
      order slightly fuzzy, meaning for a specific order, things can be called "equal" if within
      a certain range of eachother" and 2026-09-05 "the queryfacets is the order of sorting-prio
      based on facets for tags". level(c) = floor((max S' - S'(c)) / step), step = COS_NOISE
      over the median of the question's query tags' s_q. Order: level; inside a level the chunks
      with a winning edge first, by that edge's pos for temporal, why, activity, concreteness,
      descending, in the order of the winning query tag's readings for those four, largest
      first, equal readings in that order; then chunk id. HERB_V4_WALK_EQUAL=levels (the
      default); off (A7): S' descending, then chunk id.
  The winning query tag of a chunk is the one with the largest centrality_q * v_q(c), the
  earlier query tag in the list on an exact tie; its winning edge is that query tag's edge of
  the chunk with the largest w_q, the earlier edge on an exact tie. A chunk with T = 0 has no
  pair above 0: the same two rules give it the first query tag and that tag's edge for the
  order inside its level, and the meta records no winning query tag for it (-1), as for a
  chunk with no eligible edge.
  The meta records what the run read: a part a knob leaves unread is None or absent there and
  named under `not_read` - no text term and no Qs or D under HERB_V4_WALK_TEXT=off, no Qs
  under description, no lift under HERB_V4_WALK_STRUCT=off, the levels under `unused_` names
  under HERB_V4_WALK_EQUAL=off.

Every sort returns the full order. His 2026-09-13 "72 is the cut for what gets fed to the
agent to generate the output" and "make sure the artefact also follows that rule": the
72,000-character cut is the harness's, applied by `_budget_contexts` after the order;
nothing is truncated to k before it. The budget's
boundary row is delivered as text but its source ids are not credited, so the diagnostics
count the credited rows only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import threading
from pathlib import Path
import time

import numpy as np

from harness import chat
from harness.contract import ArmOutput, BuildStats, ModelUsage, unpack_generation
from harness.progress import say
from artefact import query_content as Q
from artefact import landing as LAND
from artefact import learned_relations as L
from artefact import v4_rank as R4
from artefact import v4_multikey as MK
from artefact import v4_strength as ST
from artefact import v4_walk as WK
from artefact.query_content import FACETS
from arms.artefact_facet_joint import INTERPRET_MODEL, _cached_stage, _query_cosines, _sha, _unit
from arms.artefact_v2 import _budget_contexts, _resolve_chunk
from graph.db import _readable

ROOT = Path(__file__).resolve().parents[2]
DATABASE = 'herb-eval-volmax'
RUN_ID = 'pilot_full_herb'
LEARNED_DIR = ROOT / 'output/facet_pairs/rounds/round1'
POS_COLUMNS = tuple(f + '_pos' for f in FACETS)
BANDS_FILE = LEARNED_DIR / 'bootstrap/BANDS.md'
REFITS_FILE = LEARNED_DIR / 'bootstrap/scores_b24.npz'
COS_NOISE = 0.002
BANDS = {'noise': COS_NOISE, 'paraphrase': 0.028}
SORT_MODES = ('strength', 'multikey', 'adjust_lower', 'multirank', 'concept', 'chain', 'sum',
              'walk')
DECIDER_WINDOW = 50
JOIN_MODES = ('adjust', 'mul', 'add')
ADJUST_FACETS = ('temporal', 'why', 'activity', 'concreteness')
HUB_EDGES = 500
PROBE_MODES = ('all', 'tags', 'text')
FACET_MODES = ('on', 'off')
AREA_MODES = ('off', 'first')
TAGSIDE_MODES = ('all', 'nonscope')
OFFLINE_MODES = ('off', 'on')
STRUCT_MODES = MK.STRUCT_PLACES + ('off',)
# The walk knobs: per knob its environment name, the marked step it switches, and per value the
# alternative of `v4_walk.ALTERNATIVES` or the later change of `v4_walk.CHANGES` it selects.
# None is the step's PROPOSAL, the knob's default.
WALK_KNOBS = {
    'walkfit': ('HERB_V4_WALK_FIT', 'M1', {'standing': None, 'raw': 'A1'}),
    'walkshares': ('HERB_V4_WALK_SHARES', 'M3', {'readings': None, 'equal': 'A3', 'off': 'A3b'}),
    'walkrank': ('HERB_V4_WALK_RANK', 'M3',
                 {'off': None, 'picked': 'C3r', 'percent': 'C3p', 'same': 'C3s'}),
    'walktags': ('HERB_V4_WALK_TAGS', 'M4, within a query tag',
                 {'best': None, 'pooled': 'A4a', 'peredge': 'A4e', 'sum': 'A4b',
                  'off': 'C4n'}),
    'walkqtags': ('HERB_V4_WALK_QTAGS', 'M4, across the query tags',
                  {'central': None, 'equal': 'A4c', 'sum': 'A4d'}),
    'walktext': ('HERB_V4_WALK_TEXT', 'M5',
                 {'better': None, 'off': 'A5a', 'description': 'A5b', 'clipped': 'A5c'}),
    'walkstruct': ('HERB_V4_WALK_STRUCT', 'M6',
                   {'near': None, 'off': 'A6a', 'trust1': 'A6b', 'ref0': 'A6c', 'double': 'A6d'}),
    'walkequal': ('HERB_V4_WALK_EQUAL', 'M7', {'levels': None, 'off': 'A7'}),
}
WALK_DEFAULTS = {knob: next(value for value, alternative in values.items() if alternative is None)
                 for knob, (_, _, values) in WALK_KNOBS.items()}
# The arm's defaults since 2026-10-05 evening, on his "it's time to also finish the build with
# the changes we discussed": the facets rank the picked tags and no longer multiply (SHARES off,
# RANK percent, the class a share of the closest tag's own score on his "why not just use a
# relative %?" the same night) and the structure step does not read the size of the group
# (STRUCT trust1). The walked-through PROPOSAL stays `v4_walk.chain`'s own default: each knob's
# None value.
WALK_PROPOSAL = dict(WALK_DEFAULTS)
# RANK same since later that night: the pick is the graph tags that are the same thing as the
# question tag, his "what matters is the fucking semantic relevance of that number for the tag".
WALK_DEFAULTS.update({'walkshares': 'off', 'walkrank': 'same', 'walkstruct': 'trust1'})
# The walk sort's three role knobs: per knob its environment name, its values and its default. A
# role is one of the embedder's two, `passage` the one the graph's tag vectors and chunk
# description vectors are stored in.
WALK_ROLE_KNOBS = {
    'walktagrole': ('HERB_V4_WALK_TAGROLE', ('passage', 'query'), 'passage'),
    'walkdescrole': ('HERB_V4_WALK_DESCROLE', ('passage', 'query'), 'passage'),
    'walkquestrole': ('HERB_V4_WALK_QUESTROLE', ('passage', 'query'), 'query'),
}

TAG_CYPHER = '''
MATCH (t:Tag) WHERE t.emb IS NOT NULL AND EXISTS {
    MATCH (t)<-[r:HAS_TAG]-(c:Chunk)
    WHERE r.run_id = $run AND (c)-[:product]->() }
RETURN t.name AS id, t.emb AS vector ORDER BY id
'''

CHUNK_CYPHER = '''
MATCH (c:Chunk) WHERE c.desc_emb IS NOT NULL AND EXISTS {
    MATCH (c)-[r:HAS_TAG]->() WHERE r.run_id = $run }
    AND (c)-[:product]->()
MATCH (f:File)-[:HAS_CHUNK]->(c)
RETURN c.chunk_id AS chunkId, c.desc_emb AS vector, c.locator_json AS locator,
       f.rel_path AS relpath, f.sha256 AS sha256 ORDER BY chunkId
'''

PRODUCT_CYPHER = 'MATCH (p:Product) RETURN p.name AS name ORDER BY name'

RETRIEVAL_FLAGS = {
    'interpretation': 'query_content: one querytagger call; the question in, the description, '
                      'the description-side tags and the question-side tags, five readings '
                      'each, out.',
    'interpreter_model': INTERPRET_MODEL,
    'query_tags': 'strength, multikey, adjust_lower and walk: both tag lists, each embedded '
                  'beside the description; the other sorts: the description-side list only. The '
                  'question text and the description are the two texts matched against the chunk '
                  'descriptions. Every sort but walk embeds the query side in the embedder\'s '
                  'query role; walk embeds each comparison in the role its three role knobs name.',
    'cos_noise': COS_NOISE,
    'strength': {
        'unit': 'standing(x) = (x - median) / (1.4826 * the median absolute deviation from the '
                'median) over x\'s own population; a zero spread raises. N: every graph tag '
                'except the product-name tags (casefolded); E: the edges whose tag is among '
                'them.',
        'fit': 'per query tag q of either list, the standing of cos(q,t) over the N eligible '
               'graph tags.',
        'edge_values': 'per eligible edge, query-independent: topic = the standing of cos(tag, '
                       'chunk description) over E; temporal, why, activity, concreteness each '
                       'the normal score of the edge\'s average rank in its column over E, the '
                       'standard normal quantile of (rank - 1/2) / |E|, ties sharing a rank; '
                       'the columns are the values multikey reads, their order alone is used.',
        'weight': 'w(q,e) = sum over the five of share_f(q) * value_f(e); share_f(q) = q\'s '
                  'reading over the sum of q\'s five readings; five equal shares when that sum '
                  'is 0.',
        'tag_route': 's(q,c) = max over c\'s eligible edges (t,c) of fit(q,t) + w(q,e); a chunk '
                     'with no eligible edge has none.',
        'centrality': 'cos(q, query description), both vectors from the one query-role '
                      'embedding call that embeds q, a negative one as 0, over the question\'s '
                      'largest; no positive cosine raises.',
        'tags': 'T(c) = max over q of centrality(q) * max(s(q,c), 0); 0 for a chunk with no '
                'eligible edge.',
        'description': 'D(c), Q(c) = the standing over the chunks of cos(query description, '
                       'chunk description) and of cos(raw question, chunk description); '
                       'S(c) = T(c) + max(D(c), Q(c)).',
        'structure': 'per node type (product, channel, file = the chunk\'s relpath) and chunk c '
                     'with another chunk under the same node: max(0, mean of S over the other '
                     'chunks under the node - mean of S over all chunks); the largest over a '
                     'chunk\'s channels; S\'(c) = S(c) + the three boosts; nothing is lowered, '
                     'no chunk is removed.',
        'level': 'floor((max S\' - S\'(c)) / step), step = COS_NOISE over the median of the '
                 'question\'s query tags\' fit spreads.',
        'order': 'level -> chunks with a winning edge before chunks with no eligible edge -> '
                 'the winning edge\'s four facet normal scores, descending, in the order of the '
                 'winning query tag\'s readings for temporal, why, activity, concreteness, '
                 'largest first, equal readings in that order -> chunk id; full order returned, '
                 'harness cuts.',
        'ties': 'an exact tie between two edges of a chunk goes to the earlier edge, between '
                'two query tags to the earlier query tag in the list; D where D = Q; a chunk '
                'counts once under a node.',
        'diagnostic': 'for the credited rows: each term\'s sum and its share of their total '
                      'strength, the term with the largest absolute difference per adjacent '
                      'pair, the rows taking D or Q, the levels; over all chunks the largest '
                      'boost and the chunks with a positive boost per node type.',
    },
    'multikey': {
        'edges': 'Every (q,t,c): q every query tag of both lists, t every graph tag except the '
                 'product-name tags (casefolded), c every chunk on t\'s HAS_TAG edge; no pick, '
                 'no cut.',
        'key': 'fit level floor((best fit over the question\'s edges - fit) / W), W from '
               'HERB_V4_FITEQ -> the four facets temporal, why, activity, concreteness in the '
               'order of q\'s readings for them, largest first, equal readings in that order, '
               'each floor((best value of the column over the question\'s edges - value) / '
               'the column\'s gap) -> landed -> seed distance -> topic level floor((best topic '
               'over the question\'s edges - topic) / COS_NOISE) -> description level -> '
               'question level (COS_NOISE below the best over the chunks) -> chunk id; '
               'HERB_V4_STRUCT_AT=after_fit moves landed and seed distance right after fit, '
               'off leaves both out.',
        'landed': '0 if the chunk sits in the question\'s landed area (landing.land, areas, '
                  'combine: the meet of the distinct landings), else 1; no landing: 0 for every '
                  'chunk. A capitalised word the pool chunks\' texts carry never reaches the '
                  'nearest-name pass; a landing that reaches no chunk is dropped from the meet '
                  '(both the orchestrator\'s).',
        'seed_distance': 'seeds: the chunks an edge at fit level 0 reaches; 0 a seed, 1 sharing '
                         'a [:channel] node with a seed or file-adjacent to one '
                         '(artefact_v3.file_adjacency), 2 under the same product as a seed, 3 '
                         'otherwise; channels and products read by artefact_v3.load_shape.',
        'fit_equal_widths': dict(BANDS),
        'facet_values': 'each edge\'s mean score over the 24 refits in '
                        'rounds/round1/bootstrap/scores_b24.npz, the quantity the gaps were '
                        'measured on',
        'facet_gaps': 'each column\'s own "gap (any)" (uniform edge pairs) from the per-column '
                      'table of rounds/round1/bootstrap/BANDS.md',
        'chunk_place': 'a chunk takes the place of its best edge, its first appearance in the '
                       'sorted edge list',
        'unreached': 'chunks with no eligible edge follow, by their own keys in the same order '
                     '(landed, seed distance, description level, question level, chunk id)',
        'diagnostic': f'for the adjacent pairs among the first {DECIDER_WINDOW} credited rows, '
                      'the first key that separates the two',
    },
    'adjust_lower': {
        'reach': 'Every query tag of both lists to every graph tag except the product-name '
                 'tags; fit = cos(q,t); no pick, no band, no cut.',
        'relevance': 'rel = fit(q,t) * T(t,c) * prod over temporal, why, activity, concreteness '
                     'of pct_f(t,c) ** (q_f / sum q_f), the weighted geometric mean (1 when the sum '
                     'is 0 or HERB_V4_FACETS=off); fit and topic as they are; T = topic '
                     '(HERB_V4_QTOPIC=off), or max(topic, 0) ** q_topic where q_topic > 0 and '
                     'topic where q_topic = 0 (exp); pct_f the stored percentile rank r/n.',
        'edge_combination': 'HERB_V4_EDGECOMB=sum: every (q,t) reaching c adds; max: per query tag '
                            'the best graph tag, summed over query tags; best: the single '
                            'largest (q,t) term over every query tag and graph tag reaching c.',
        'description': 'HERB_V4_DESCJOIN=key: on an exact tie of the tag score, '
                       'cos(description, chunk desc), then cos(question, chunk desc), each '
                       'levelled at COS_NOISE below its best; mul: S * max(cos(description), 0) * '
                       'max(cos(question), 0), continuous.',
        'order': 'reached before unreached -> score descending, continuous -> (key: description '
                 'level -> question level) -> landing meet first -> chunk id; full order '
                 'returned, harness cuts.',
    },
    'multirank': {
        'best_edge': 'Per chunk its best (q,t) edge by strength = fit * topic over every query tag '
                     'and every non-product graph tag (casefolded).',
        'key': 'strength level floor((best strength of the question - strength) / COS_NOISE), the '
               'same quantity that chose the edge -> the five levels of that edge '
               'in the order of the five readings of its query tag, largest first, equal '
               'readings in facet order -> description level -> question level -> landing -> id.',
        'levels': 'facets: floor((column max - stored score) / flip gap) over all edges, the gap '
                  'the pooled same-chunk retrain flip gap from bootstrap/BANDS.md; topic: '
                  'floor((max cosine - cosine) / COS_NOISE) over all edges.',
        'unreached': 'Chunks with no non-product edge follow, by description level, question '
                     'level, landing, id.',
    },
    'concept': {
        'reach': 'Every query tag to every graph tag except the product-name tags; fit = cos(q,t); '
                 'no pick, no band.',
        'relevance': 'rel = fit+(q,t) * topic+(t,c) * (1 + (1/4) sum over temporal, why, activity, '
                     'concreteness of r_f v_f); x+ = max(x, 0); T_q(c) = max over the chunk\'s '
                     'edges; S(c) = sum_q T_q(c).',
        'text': 'D(c) = cos+(question, chunk desc) + cos+(description, chunk desc).',
        'join': 'HERB_V4_JOIN=adjust: S*(1+D) (default); mul: S*D; add: S+D. All three are the '
                'arm\'s constructions.',
        'adjust_facets': list(ADJUST_FACETS),
        'order': 'score desc -> chunk id; full order returned, harness cuts. No area key.',
        'hub_edges': HUB_EDGES,
    },
    'chain': {
        'fit_level': 'floor((best_fit_all - fit(q,t)) / COS_NOISE), best_fit_all the highest fit '
                     'of any query tag to any graph tag; one scale for the question; no cut.',
        'relevance': 'topic(t,c) * (1 + sum_f r_f v_f / sum_f r_f), five facets, stored _pos '
                     'columns; levelled floor((max rel at the fit level - rel) / COS_NOISE) over '
                     'every edge at that fit level; the anchor is the question\'s own pool.',
        'description': 'cos(the querytagger description, chunk description), continuous, after '
                       'the tag keys.',
        'order': 'per chunk its best (fit_level, rel_level) over every (q,t) reaching it; reached '
                 'by (best key, -d, id); unreached after, by (-d, id). No text probe, no area key.',
    },
    'sum': {
        'pick': 'Per query tag, graph tags with fit >= best fit - band.',
        'bands': dict(BANDS),
        'score': 'sum_q sum_t fit(q,t) * topic(t,c) * (1 + sum_f r_f v_f / sum_f r_f) '
                 '+ sum_text cos(text, chunk description).',
        'scale': 'The tag part and the text part are added 1:1 with nothing making them '
                 'commensurate.',
        'area': 'landing.combine meet; HERB_V4_AREA=first sorts in-area first, a cut under a '
                'budget.',
        'order': 'area key (when on) -> score desc -> chunk id.',
    },
    'walk': {
        'chain': 'v4_walk.chain, the one implementation tools/walkthrough.py prints from and '
                 'this arm sorts by. N: every graph tag except the product-name tags '
                 '(casefolded); E: the edges whose tag is among them. Every step is the '
                 'orchestrator\'s calculation. M1 to M7 are marked steps awaiting his word: each '
                 'knob\'s default is the step\'s PROPOSAL, each other value the alternative of '
                 'the walk-through it names or one of the two changes built after it (C3r: '
                 'HERB_V4_WALK_RANK=picked, the four facets ranking the edges inside one class '
                 'of closeness, the class one self-difference wide; C4n: HERB_V4_WALK_TAGS=off, '
                 'no tag term), and the build settles none of them. A phrase '
                 'standing in both tag lists is two query tags: it enters twice, once with each '
                 'list\'s readings.',
        'roles': 'each comparison is embedded in one of the embedder\'s two roles; the graph\'s '
                 'tag vectors and chunk description vectors are stored in the passage role '
                 '(test/graph/reembed_herb_eval.py). HERB_V4_WALK_TAGROLE: the role of the '
                 'question\'s tags, both lists, for their cosines to the graph tags (M1) - '
                 'passage (the default, on his 2026-10-05 ruling: a tag against a tag is '
                 'compared in the same role on both sides) or query, the role every other sort '
                 'embeds them in. HERB_V4_WALK_DESCROLE: the role of the query description for '
                 'its cosines to the chunk descriptions (M5); HERB_V4_WALK_QUESTROLE: the role '
                 'of the raw question for its cosines to the chunk descriptions (M5) - each '
                 'passage or query; the description defaults to passage (his 2026-10-05 ruling '
                 'that everything embedded for the artefact is embedded the same way), the raw '
                 'question to query (his "yes to the question" the same night: it is the one '
                 'text that is a question). The centrality (M4) compares '
                 'a tag with the query description in one role for both: the passage role when '
                 'the tags\' and the description\'s knobs both say passage, the query role in '
                 'every other combination - the orchestrator\'s rule, unruled. Under the '
                 'defaults the tags, the description and the centrality are in the passage '
                 'role and the raw question in the query role; each text is embedded once '
                 'per call, the description beside each tag list (a repeat is read from the '
                 'rows kept on the side); all three knobs at query reproduce the 17 runs of '
                 '2026-10-05 08:28Z-09:51Z.',
        'M1_fit': 'per query tag q of either list, z_q(t) = the standing of cos(q,t) over the N '
                  'eligible graph tags, (cos - median) / (1.4826 * the median absolute deviation '
                  'from the median); fit_q(t) = max(z_q(t), 0); a zero spread raises. '
                  'HERB_V4_WALK_FIT=raw (A1): fit_q(t) = cos(q,t); under raw more than the fit '
                  'is exchanged: the tag term T is in raw cosines while the text side stays in '
                  'standings, the lifts are taken on the sum of the two, and the level step '
                  'stays COS_NOISE over the median s_q.',
        'M2_positions': 'per eligible edge, query-independent: pos_k(e) = the edge\'s average '
                        'rank in column k over E (1 the smallest, ties sharing a rank) / |E|; '
                        'the columns topic = cos(tag, chunk description) and temporal, why, '
                        'activity, concreteness, the values multikey reads. Ranking topic, a '
                        'cosine, like the four stored columns is the orchestrator\'s. No '
                        'alternative, no knob.',
        'M3_weight': 'share_q = q\'s five readings over their sum, five equal shares when that '
                     'sum is 0; R_q(e) = sum_k share_q[k] * pos_k(e); w_q(e) = fit_q(t) * R_q(e) '
                     '/ 0.5. 0.5 stands for the middle position: an edge at the middle rank of '
                     'all five columns has R = (|E| + 1) / (2 |E|) and the factor (|E| + 1) / '
                     '|E|, not 1. For a positive fit a factor above 1 raises the closeness and '
                     'one below 1 lowers it; a fit of 0 stays 0; under HERB_V4_WALK_FIT=raw a '
                     'graph tag with a negative cosine turns it round. '
                     'HERB_V4_WALK_SHARES=equal (A3): five equal shares; off (A3b): w_q(e) = '
                     'fit_q(t). Under equal and under off the readings still give the facet '
                     'order inside a level; under off the edge\'s positions leave the weight '
                     'and the order inside a level is still the winning edge\'s four facet '
                     'positions.',
        'M4_tags': 'v_q(c) = the largest w_q over c\'s eligible edges, 0 with none; no '
                   'correction for n_c, the number of c\'s eligible edges. '
                   'HERB_V4_WALK_TAGS=pooled (A4a): in place of v the k-th largest w_q over E, '
                   'k = ceil(p * |E|), p = 1 - (1 - K / |E|)^n_c, K the eligible edges with w_q '
                   '>= v; peredge (A4e): in place of v the k-th largest fit_q over N, '
                   'k = ceil(p * |N|), p = 1 - the product over c\'s edges i of (1 - K_i / |N|), '
                   'K_i the eligible graph tags t with fit_q(t) * R_q(i) / 0.5 >= v; sum (A4b): '
                   'in place of v the sum of w_q over c\'s edges. The sum stands against his '
                   '2026-09-10 sentence on parts and is kept as an alternative the walk-through '
                   'measured: under it the tag term grows with the chunk\'s number of eligible '
                   'edges while the text side and the level step stay as they are.',
        'M4_query_tags': 'centrality_q = cos(q, query description), both vectors from the one '
                         'embedding call that embeds q beside the description, in the '
                         'centrality\'s role (roles), a negative one as 0, over '
                         'the question\'s largest; no positive cosine raises; T(c) = max over q '
                         'of centrality_q * v_q(c). HERB_V4_WALK_QTAGS=equal (A4c): centrality '
                         '1; sum (A4d): the sum over q in place of the max. The sum stands '
                         'against his 2026-09-10 sentence on parts and is kept as an '
                         'alternative the walk-through measured: under it the tag term grows '
                         'with the number of query tags, a phrase in both lists counted twice, '
                         'while the text side and the level step stay as they are.',
        'M5_text': 'D(c), Qs(c) = the standing over the chunks of cos(query description, chunk '
                   'description) and of cos(raw question, chunk description), not clipped; '
                   'S(c) = T(c) + max(D(c), Qs(c)). HERB_V4_WALK_TEXT=off (A5a): S = T; '
                   'description (A5b): S = T + D; clipped (A5c): S = T + max(D, Qs, 0).',
        'M6_structure': 'two groupings: product; near group, a connected component of the file '
                        'adjacency (artefact_v3.file_adjacency) with at least two chunks. '
                        'Product: x = S, reference the mean of S over the chunks. Near: x = S - '
                        'the mean of S over the chunk\'s product, reference(c) the mean of x '
                        'over the chunks of c\'s record kind that sit in a near group. '
                        'raw(c,g) = the mean of x over g\'s members other than c - reference(c); '
                        'on x - reference: sigma2 the pooled within-group variance, tau2 = '
                        'max(0, (SSB - (G - 1) * sigma2) / (M - sum n_g^2 / M)), SSB = sum_g '
                        'n_g * (mean_g - the mean over the memberships)^2, G the groups, M the '
                        'memberships; trust(g) = tau2 / (tau2 + sigma2 / (n_g - 1)); lift(c,g) '
                        '= max(0, trust(g) * raw(c,g)); S\'(c) = S(c) + the two lifts; nothing '
                        'is lowered, no chunk is removed. HERB_V4_WALK_STRUCT=off (A6a): S\' = '
                        'S; trust1 (A6b): trust 1; ref0 (A6c): near with reference 0; double '
                        '(A6d): three groupings, product, channel and record (= near group), '
                        'channel and record on x with reference 0, the largest lift over a '
                        'chunk\'s channels, tau2 = max(0, SSB / M - G * sigma2 / M), S\' = S + '
                        'the three lifts.',
        'M7_order': 'step = COS_NOISE over the median of the question\'s query tags\' s_q; '
                    'level(c) = floor((max S\' - S\'(c)) / step); order: level -> chunks with a '
                    'winning edge before chunks with no eligible edge -> the winning edge\'s pos '
                    'for temporal, why, activity, concreteness, descending, in the order of the '
                    'winning query tag\'s readings for those four, largest first, equal '
                    'readings in that order -> chunk id; full order returned, harness cuts. '
                    'HERB_V4_WALK_EQUAL=off (A7): S\' descending -> chunk id.',
        'ties': 'the winning query tag of a chunk: the largest centrality_q * v_q(c), the '
                'earlier query tag in the list on an exact tie; its winning edge: that query '
                'tag\'s edge of the chunk with the largest w_q, the earlier edge on an exact '
                'tie. A chunk with T = 0 has no pair above 0: the same two rules give it the '
                'first query tag and that tag\'s edge for the order inside its level.',
        'knobs': {env: {'step': step,
                        'values': {value: alternative or 'PROPOSAL'
                                   for value, alternative in values.items()}}
                  for env, step, values in WALK_KNOBS.values()},
        'role_knobs': {env: {'values': list(values), 'default': default}
                       for env, values, default in WALK_ROLE_KNOBS.values()},
        'diagnostic': 'embedding_roles: the role of the tags, the description, the question '
                      'and the centrality, and per tag list the vector sha256 of each '
                      'embedding call by role. '
                      'For the credited rows: per row T, the side, each grouping\'s lift, S\', '
                      'the level and the winning query tag, -1 for a chunk with no eligible '
                      'edge or with T = 0; each term\'s sum and its share of their total '
                      'strength, the rows whose Qs stands above their D, the levels; over all '
                      'chunks per grouping the groups, memberships, sigma2, tau2, the chunks '
                      'with a lift above 0 and the largest lift; the phrases standing in both '
                      'tag lists; the switches of v4_walk.chain the knobs set and the '
                      'alternatives they name. A part a knob leaves unread is None or absent '
                      'and named under not_read: no text term, no text bulk or spread and no '
                      'Qs-above-D count under HERB_V4_WALK_TEXT=off, the description\'s alone '
                      'and no count under description; no lift and no grouping under '
                      'HERB_V4_WALK_STRUCT=off; no description cosines of the query tags under '
                      'HERB_V4_WALK_QTAGS=equal; the query tags with equal shares are all of '
                      'them under HERB_V4_WALK_SHARES=equal and None under off; under '
                      'HERB_V4_WALK_EQUAL=off levels_order_the_rows is false and the level '
                      'numbers the chain still computes stand under unused_ names.',
    },
    'facet_values': 'round1 stored scores and _pos columns, query-independent. strength reads '
                    'each edge\'s mean over the 24 bootstrap refits as the normal score of its '
                    'rank in the column over the eligible edges; walk reads the same means as '
                    'the edge\'s average rank in the column over the eligible edges, over their '
                    'number; multikey reads '
                    'each edge\'s mean over the 24 bootstrap refits, levelled below the '
                    'question\'s best at each column\'s own gap; adjust_lower and multirank '
                    'read the stored scores through the rank layer '
                    '(percentile r/n; levels at the pooled flip gap); concept, chain and sum '
                    'read the _pos columns directly, each by the form its own entry states.',
    'topic_edge_value': 'cos(tag vector, chunk description vector) from the live graph.',
    'tagside': 'nonscope gives product-named graph tags no fit level (chain) / no pick (sum); the '
               'best fit is taken over the remaining tags.',
    'cut': 'Full order returned; the harness cuts at the character budget.',
    'offline': 'HERB_V4_OFFLINE=on: a question whose querytagger answer is not a good cached '
               'answer raises before any model call; off: a cache miss asks the model.',
    'knobs': ('HERB_V4_SORT', 'HERB_V4_FITEQ', 'HERB_V4_STRUCT_AT', 'HERB_V4_QTOPIC',
              'HERB_V4_EDGECOMB', 'HERB_V4_DESCJOIN', 'HERB_V4_JOIN', 'HERB_V4_BAND',
              'HERB_V4_PROBES', 'HERB_V4_FACETS', 'HERB_V4_AREA', 'HERB_V4_TAGSIDE',
              'HERB_V4_OFFLINE', *(env for env, _, _ in WALK_KNOBS.values()),
              *(env for env, _, _ in WALK_ROLE_KNOBS.values())),
    'defaults': {'HERB_V4_SORT': 'walk', 'HERB_V4_FITEQ': 'noise',
                 'HERB_V4_STRUCT_AT': 'after_facets', 'HERB_V4_QTOPIC': 'off',
                 'HERB_V4_EDGECOMB': 'sum', 'HERB_V4_DESCJOIN': 'key', 'HERB_V4_JOIN': 'adjust', 'HERB_V4_BAND': 'noise',
                 'HERB_V4_PROBES': 'all',
                 'HERB_V4_FACETS': 'on', 'HERB_V4_AREA': 'off', 'HERB_V4_TAGSIDE': 'all',
                 'HERB_V4_OFFLINE': 'off',
                 **{env: WALK_DEFAULTS[knob] for knob, (env, _, _) in WALK_KNOBS.items()},
                 **{env: default for env, _, default in WALK_ROLE_KNOBS.values()}},
    'status': 'Constructed arm; under strength the spread unit, the rank-to-normal step, the '
              'weighted mean of the five edge values, the plus of fit and weight, the relative '
              'centrality and the positive part, max(D, Q) and its plus, the leave-one-out '
              'boost and the level step are the orchestrator choices, the tie rules the '
              'arm\'s; under multikey the one fit anchor for the question, the fit '
              'equal width (noise and paraphrase both kept, noise the default), the refit mean '
              'as the facet value and the column\'s "gap (any)" flip gap as a facet\'s "equal", '
              'the tie order of equal readings, '
              'topic -> description -> question, a chunk at its best edge, the unreached '
              'tail, the landed and seed-distance keys and both their places, the corpus-word '
              'rule on the nearest-name pass and the dropped empty landings are the '
              'orchestrator choices; under adjust_lower the product-of-powers form, the '
              'normalisation of the readings by their sum, the percentile convention r/n, the '
              'sum, max or single best over edges, the key join with the description before the question, and the '
              'topic handling under exp are '
              'the orchestrator choices; under multirank the best edge by fit * topic, COS_NOISE as the '
              'step on that product (not a cosine), the tie order of equal readings, and '
              'COS_NOISE as the topic equal are the orchestrator choices; under concept the max-per-query-tag, the sum over query tags '
              '(against his 2026-09-10 sentence on parts), the four-facet mean, the clipping at 0 '
              'and the three joins are the arm\'s; the fit grid (COS_NOISE steps anchored at the question\'s best fit, '
              'one level scale for every query tag), the relevance form and its levelling are '
              'not his rulings; under walk every step M1 to M7 is the orchestrator\'s '
              'calculation, marked and not settled - the standing clipped at 0 as the fit, the '
              'average rank over |E| as an edge value\'s position, topic ranked like the four '
              'stored columns, the shares over the five '
              'positions and the division by 0.5, the chunk\'s best w with no correction for '
              'its tag count, the relative centrality and the max over the query tags, '
              'max(D, Qs) and its plus, the product and near-group lifts with their '
              'references, variances and trust, and the level step, each with its alternative '
              'behind a HERB_V4_WALK_* knob (M2 has none), the two sums among the alternatives '
              '(against his 2026-09-10 sentence on parts), a phrase in both tag lists entering '
              'twice, and the tie rules; the passage role of the tags and the description is '
              'his 2026-10-05 ruling (everything embedded for the artefact the same way), the '
              'query role of the raw question his "yes to the question" the same night, the '
              'one-role rule of the centrality the orchestrator\'s, unruled; '
              'HERB_V4_WALK_RANK=picked (C3r) and HERB_V4_WALK_TAGS=off (C4n) were built after '
              'the walk-through, the first on his 2026-10-05 words on the facets as a ranking '
              'in the orchestrator\'s form, the second for a measurement. Nothing written to '
              'the graph.',
}


def _choice(name, allowed, default):
    value = os.environ.get(name, default)
    if value not in allowed:
        raise ValueError(f'{name} must be one of {allowed}, got {value!r}')
    return value


def knobs():
    """Read at call time, never at import, so a run's flags are the run's own."""
    return {'sort': _choice('HERB_V4_SORT', SORT_MODES, 'walk'),
            'fiteq': _choice('HERB_V4_FITEQ', tuple(BANDS), 'noise'),
            'structat': _choice('HERB_V4_STRUCT_AT', STRUCT_MODES, 'after_facets'),
            'qtopic': _choice('HERB_V4_QTOPIC', R4.QTOPIC_MODES, 'off'),
            'edgecomb': _choice('HERB_V4_EDGECOMB', R4.EDGECOMB_MODES, 'sum'),
            'descjoin': _choice('HERB_V4_DESCJOIN', R4.DESCJOIN_MODES, 'key'),
            'join': _choice('HERB_V4_JOIN', JOIN_MODES, 'adjust'),
            'band': _choice('HERB_V4_BAND', tuple(BANDS), 'noise'),
            'probes': _choice('HERB_V4_PROBES', PROBE_MODES, 'all'),
            'facets': _choice('HERB_V4_FACETS', FACET_MODES, 'on'),
            'area': _choice('HERB_V4_AREA', AREA_MODES, 'off'),
            'tagside': _choice('HERB_V4_TAGSIDE', TAGSIDE_MODES, 'all'),
            'offline': _choice('HERB_V4_OFFLINE', OFFLINE_MODES, 'off'),
            **{knob: _choice(env, tuple(values), WALK_DEFAULTS[knob])
               for knob, (env, _, values) in WALK_KNOBS.items()},
            **{knob: _choice(env, values, default)
               for knob, (env, values, default) in WALK_ROLE_KNOBS.items()}}


KNOB_ENV = {'sort': 'HERB_V4_SORT', 'fiteq': 'HERB_V4_FITEQ', 'structat': 'HERB_V4_STRUCT_AT',
            'qtopic': 'HERB_V4_QTOPIC',
            'edgecomb': 'HERB_V4_EDGECOMB',
            'descjoin': 'HERB_V4_DESCJOIN', 'join': 'HERB_V4_JOIN', 'band': 'HERB_V4_BAND',
            'probes': 'HERB_V4_PROBES',
            'facets': 'HERB_V4_FACETS', 'area': 'HERB_V4_AREA', 'tagside': 'HERB_V4_TAGSIDE',
            'offline': 'HERB_V4_OFFLINE',
            **{knob: env for knob, (env, _, _) in WALK_KNOBS.items()},
            **{knob: env for knob, (env, _, _) in WALK_ROLE_KNOBS.items()}}
READ_BY = {'strength': ('sort', 'offline'),
           'multikey': ('sort', 'fiteq', 'structat', 'offline'),
           'adjust_lower': ('sort', 'qtopic', 'edgecomb', 'descjoin', 'facets', 'offline'),
           'multirank': ('sort', 'offline'),
           'concept': ('sort', 'join', 'facets', 'offline'),
           'chain': ('sort', 'facets', 'tagside', 'offline'),
           'sum': ('sort', 'band', 'probes', 'facets', 'area', 'tagside', 'offline'),
           'walk': ('sort', *WALK_KNOBS, *WALK_ROLE_KNOBS, 'offline')}


def knob_record(flags):
    """Every knob by its environment name, and which of them the active sort reads."""
    read = READ_BY[flags['sort']]
    record = {'active': {KNOB_ENV[k]: v for k, v in flags.items()},
              'read_by_active_sort': [KNOB_ENV[k] for k in read],
              'ignored_by_active_sort': [KNOB_ENV[k] for k in flags if k not in read]}
    if flags['sort'] in ('strength', 'multikey', 'adjust_lower', 'multirank', 'concept', 'walk'):
        record['product_name_tags_excluded_by_the_sort'] = True
    return record


def walk_switches(flags):
    """The switches of `v4_walk.chain` the walk knobs set, and per knob that is off its PROPOSAL
    the alternative of the walk-through (`v4_walk.ALTERNATIVES`) or the later change
    (`v4_walk.CHANGES`) it names, by environment name."""
    selected = {env: values[flags[knob]] for knob, (env, _, values) in WALK_KNOBS.items()
                if values[flags[knob]] is not None}
    named = {**WK.ALTERNATIVES, **WK.CHANGES}
    switches = {}
    for alternative in selected.values():
        switches.update(named[alternative])
    return switches, selected


def walk_roles(flags):
    """The embedder role of each comparison of the walk sort: the question's tags against the
    graph tags, the query description against the chunk descriptions and the raw question
    against the chunk descriptions as their three knobs say; a tag against the query
    description (the centrality) in one role for both, the passage role when the tags' and the
    description's knobs both say passage and the query role in every other combination."""
    tags, description = flags['walktagrole'], flags['walkdescrole']
    return {'tags': tags, 'description': description, 'question': flags['walkquestrole'],
            'centrality': 'passage' if tags == description == 'passage' else 'query'}


def record_run_knobs():
    """The knobs this process runs under, into RETRIEVAL_FLAGS, which the harness writes into the
    run manifest as its retrieval_flags."""
    RETRIEVAL_FLAGS['knobs_at_prepare'] = knob_record(knobs())


def cache_root():
    return Path(os.environ.get('HERB_V4_CACHE',
                               str(ROOT / 'output/private/artefact_v4_cache')))


@dataclass(frozen=True)
class Prepared:
    chunk_rows: tuple
    chunk_ids: tuple
    chunk_kinds: tuple
    graph_tags: tuple
    product_tags: tuple
    nonscope_eligible: np.ndarray
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray
    edge_tag: np.ndarray
    edge_chunk: np.ndarray
    edge_topic: np.ndarray
    edge_pos: np.ndarray
    landings: tuple
    driver: object
    cache_dir: Path
    provenance: dict
    build_stats: BuildStats
    rank_layer: R4.RankLayer | None = None
    casefold_eligible: np.ndarray | None = None
    multikey_layer: MK.MultikeyLayer | None = None
    structure: MK.Structure | None = None
    corpus_words: frozenset | None = None
    strength_layer: ST.StrengthLayer | None = None
    walk_layer: dict | None = None

    def close(self):
        """Release the graph driver the areas read from."""
        if self.driver is not None:
            self.driver.close()


def _read_positions(path):
    """The five _pos columns in FACETS order, by name, and the record kind, per edge."""
    pos, kind = {}, {}
    with path.open('r', encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row['tag'], row['chunk_id'])
            values = tuple(float(row[c]) for c in POS_COLUMNS)
            if any(not np.isfinite(v) or not 0. <= v <= 1. for v in values):
                raise ValueError('A stored facet position is not a finite value in [0,1]')
            pos[key] = values
            kind[row['chunk_id']] = row['kind']
    return pos, kind


def _corpus_words(chunk_rows):
    """The casefolded tokens of every pool chunk's text, the text `_resolve_chunk` returns,
    split as `landing.land` splits a question."""
    words, docs, started = set(), {}, time.perf_counter()
    for done, row in enumerate(chunk_rows, 1):
        text, _ = _resolve_chunk(row, docs)
        words.update(word.casefold() for word, _, _ in LAND._tokens(text))
        if done % 1000 == 0:
            say(f'artefact_v4: corpus words: {done}/{len(chunk_rows)} chunks read '
                f'({time.perf_counter() - started:.1f}s)')
    return frozenset(words)


def _strength_layer(chunk_rows, edge_tag, edge_chunk, edge_topic, facet_values, eligible,
                    structure):
    """The strength sort's query-independent layer: the eligible edges' five values in one unit,
    and each chunk's product, channels and file, the file being its relpath."""
    paths = [row.get('relpath') for row in chunk_rows]
    if any(not isinstance(path, str) or not path for path in paths):
        raise ValueError('A pool chunk has no file path')
    at = {path: i for i, path in enumerate(sorted(set(paths)))}
    return ST.build_layer(edge_tag, edge_chunk, edge_topic, facet_values, eligible,
                          structure.product, structure.channel_ptr, structure.channels,
                          np.array([at[path] for path in paths], dtype=np.int64))


def _self_difference(graph_tags, eligible, tag_vectors, chunk_vectors):
    """How far a graph tag's own name, embedded in the passage role, lands from its own stored
    vector, over `v4_walk.draw_probes`' eligible graph tags (`v4_walk.self_difference`): the
    width of "equally close" under HERB_V4_WALK_RANK=picked. The names are embedded as the
    graph embedded them (`graph.db._readable`) through `_query_cosines`, so each is kept on
    the side after its first time."""
    probes = WK.draw_probes(eligible)
    names = [_readable(graph_tags[i]) for i in probes.tolist()]
    matrices, used, recipe = _query_cosines(
        names[0], names, _QueryAxes(tag_vectors, chunk_vectors), 'passage')
    return {**WK.self_difference(matrices['query_tag_cosines'], probes), 'role': 'passage',
            'seed': WK.PROBE_SEED, 'embedding': recipe['vector_sha256'],
            'embedded_now': int(used.calls), 'embedding_seconds': float(used.time_s)}


_WIDTH_LOCK = threading.Lock()


def _walk_width(prepared):
    """The walk layer's self-difference, measured once per prepared graph at the first
    question that needs it and kept in the layer (`_self_difference`; the largest over the
    probes is the width). Query-independent: the caller measures it before the question's
    clock starts."""
    layer = prepared.walk_layer
    if layer is None:
        raise ValueError('walk needs the prepared walk layer')
    with _WIDTH_LOCK:
        if layer.get('self_difference') is None:
            measured = _self_difference(prepared.graph_tags, layer['eligible'],
                                        prepared.tag_vectors, prepared.chunk_vectors)
            say(f'artefact_v4: a graph tag\'s own name lands {measured["median"]:.4f} from its '
                f'own vector at the median, {measured["largest"]:.4f} at the largest, over '
                f'{measured["probes"]} names in the passage role; its own tag the closest on '
                f'{measured["own_tag_closest"]}; embedded now {measured["embedded_now"]}')
            layer['self_difference_measured'] = measured
            layer['self_difference'] = measured['largest']
    return layer.get('self_difference_measured') or {'largest': layer['self_difference'],
                                                     'given_to_the_layer': True}


def _walk_layer(chunk_ids, chunk_kinds, edge_tag, edge_chunk, edge_topic, facet_values, eligible,
                structure, facet_gaps=None, self_difference=None, same_level=None):
    """The walk sort's query-independent layer, `v4_walk.build_layer` on the arm's arrays: the
    eligible edges' five positions, each chunk's record kind and product, the channels, and the
    near groups from the file adjacency; with the four facet gaps and the self-difference also
    each edge's four facet classes, for HERB_V4_WALK_RANK=picked. Its arrays are read-only."""
    layer = WK.build_layer({
        'chunk_ids': chunk_ids, 'chunk_kinds': chunk_kinds, 'eligible': eligible,
        'edge_tag': edge_tag, 'edge_chunk': edge_chunk, 'edge_topic': edge_topic,
        'edge_facets': facet_values, 'product': structure.product,
        'channel_ptr': structure.channel_ptr, 'channels': structure.channels,
        'adjacency_ptr': structure.adjacency_ptr, 'adjacency': structure.adjacency,
        'facet_gaps': facet_gaps, 'self_difference': self_difference,
        'same_level': same_level})
    for value in (*layer.values(), *(a for pair in layer['groups'].values() for a in pair)):
        if isinstance(value, np.ndarray):
            value.setflags(write=False)
    return layer


def _walk_counts(layer):
    """The walk layer in counts."""
    near = layer['near']
    return {'eligible_graph_tags': int(layer['eligible'].sum()),
            'eligible_edges': int(layer['edges'].size),
            'chunks': int(layer['chunks']),
            'chunks_with_an_eligible_edge': int((layer['n_c'] > 0).sum()),
            'position_columns': list(R4.ALL_FACETS),
            'record_kinds': {name: int((layer['kind'] == code).sum())
                             for code, name in enumerate(layer['kind_names'])},
            'products': int(np.unique(layer['product']).size),
            'chunks_with_a_channel': int(np.unique(layer['groups']['channel'][0]).size),
            'near_groups': int(near.max()) + 1,
            'chunks_in_a_near_group': int((near >= 0).sum())}


def prepare_over_corpus(corpus) -> Prepared:
    """Graph vectors, the learned layer and the resolved structure names, once."""
    started = time.perf_counter()
    record_run_knobs()
    say(f'artefact_v4: loading the learned facet layer from {LEARNED_DIR.name}')
    from graph.db import _driver
    learned = L.load(LEARNED_DIR)
    positions, kinds = _read_positions(LEARNED_DIR / 'scores.jsonl')
    say(f'artefact_v4: {len(learned.endpoints)} learned edges, {len(positions)} stored positions; '
        f'reading {DATABASE} tag vectors')
    cache = cache_root()
    driver = _driver()
    try:
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            tag_rows = session.execute_read(lambda tx: list(tx.run(TAG_CYPHER, run=RUN_ID)))
            say(f'artefact_v4: {len(tag_rows)} tag vectors read, reading chunk descriptions')
            chunk_rows = session.execute_read(lambda tx: list(tx.run(CHUNK_CYPHER, run=RUN_ID)))
            say(f'artefact_v4: {len(chunk_rows)} chunk vectors read, reading product names')
            product_names = session.execute_read(
                lambda tx: [r['name'] for r in tx.run(PRODUCT_CYPHER)])
            say(f'artefact_v4: {len(product_names)} products, resolving structure names')
            # landing.resolve_names keys its cache on NEO4J_DATABASE; this arm pins the
            # database, so the key names the database actually read.
            held = os.environ.get('NEO4J_DATABASE')
            os.environ['NEO4J_DATABASE'] = DATABASE
            try:
                landings = tuple(LAND.resolve_names(session, cache=cache / 'landing_names.json'))
            finally:
                if held is None:
                    os.environ.pop('NEO4J_DATABASE', None)
                else:
                    os.environ['NEO4J_DATABASE'] = held
        graph_tags = tuple(r['id'] for r in tag_rows)
        chunk_ids = tuple(r['chunkId'] for r in chunk_rows)
        if len(set(graph_tags)) != len(graph_tags) or len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError('Duplicate graph tag or chunk identity')
        tag_vectors = _unit(np.asarray([r['vector'] for r in tag_rows], dtype=np.float32))
        chunk_vectors = _unit(np.asarray([r['vector'] for r in chunk_rows], dtype=np.float32))
        at = {name: i for i, name in enumerate(graph_tags)}
        ci = {name: i for i, name in enumerate(chunk_ids)}
        missing = [e for e in learned.endpoints if e[0] not in at or e[1] not in ci]
        if missing:
            raise ValueError(f'{len(missing)} learned endpoints are absent from the graph')
        edge_tag = np.array([at[t] for t, _ in learned.endpoints], dtype=np.int64)
        edge_chunk = np.array([ci[c] for _, c in learned.endpoints], dtype=np.int64)
        edge_topic = np.einsum('ij,ij->i', tag_vectors[edge_tag], chunk_vectors[edge_chunk])
        absent = [e for e in learned.endpoints if e not in positions]
        if absent:
            raise ValueError(f'{len(absent)} learned endpoints carry no stored facet positions')
        edge_pos = np.asarray([positions[e] for e in learned.endpoints], dtype=np.float64)
        chunk_kinds = tuple(kinds.get(cid, '') for cid in chunk_ids)
        edgeless = int((np.bincount(edge_chunk, minlength=len(chunk_ids)) == 0).sum())
        tagless = int((np.bincount(edge_tag, minlength=len(graph_tags)) == 0).sum())
        if tagless:
            raise ValueError(f'{tagless} graph tags carry no edge into the product-linked pool')
        negative_topic = int((edge_topic < 0).sum())
        say(f'artefact_v4: {edgeless} chunks carry no learned edge; '
            f'{negative_topic} edges have a negative topic cosine')
        products = set(product_names)
        product_tags = tuple(name for name in graph_tags if name in products)
        nonscope_eligible = np.array([name not in products for name in graph_tags], dtype=bool)
        folded = {name.casefold() for name in product_names}
        casefold_eligible = np.array([name.casefold() not in folded for name in graph_tags],
                                     dtype=bool)
        casefold_eligible.setflags(write=False)
        case_variants = int((~casefold_eligible).sum()) - len(product_tags)
        say(f'artefact_v4: {int((~casefold_eligible).sum())} graph tags equal a product name '
            f'casefolded ({case_variants} of them in another case)')
        for array in (tag_vectors, chunk_vectors, edge_tag, edge_chunk, edge_topic, edge_pos,
                      nonscope_eligible):
            array.setflags(write=False)
        gap, gap_source = R4.read_flip_gap(BANDS_FILE)
        say(f'artefact_v4: retrain flip gap {gap} score units ({BANDS_FILE.name} line '
            f'{gap_source["line"]}); building the percentile and level layer')
        rank_layer = R4.build_layer(edge_pos, learned.raw_scores, edge_topic, gap)
        facet_gaps, facet_gap_source = MK.read_facet_gaps(BANDS_FILE)
        say(f'artefact_v4: reading the refit means for multikey from {REFITS_FILE.name}')
        refit_means, refit_source = MK.read_refit_means(REFITS_FILE, learned.endpoints)
        multikey_layer = MK.build_layer(refit_means, facet_gaps, facet_gap_source, refit_source)
        say('artefact_v4: multikey facet values are each edge\'s mean over '
            f'{refit_source["draws"]} refits; per-facet flip gaps '
            + ', '.join(f'{f} {g}' for f, g in zip(R4.ADJUST_FACETS, facet_gaps))
            + f' ({BANDS_FILE.name}, column "{facet_gap_source["column"]}", lines '
            + ', '.join(str(facet_gap_source['lines'][f]) for f in R4.ADJUST_FACETS) + ')')
        say('artefact_v4: reading each chunk\'s channels and product, and the file adjacency, '
            'for the multikey structure keys')
        from arms.artefact_v3 import file_adjacency, load_shape
        with driver.session(database=DATABASE, default_access_mode='READ') as session:
            shape = session.execute_read(lambda tx: load_shape(
                tx, list(chunk_ids), ci, edge_tag, edge_chunk, list(graph_tags)))
        if (shape['product'] < 0).any():
            raise ValueError(f'{int((shape["product"] < 0).sum())} pool chunks have no product '
                             'in the structure read')
        say(f'artefact_v4: reading the corpus words of the {len(chunk_rows)} pool chunks for the '
            'landing')
        corpus_words = _corpus_words([dict(r) for r in chunk_rows])
        say(f'artefact_v4: {len(corpus_words)} distinct corpus words')
        adjacency = file_adjacency([dict(r) for r in chunk_rows])
        structure = MK.build_structure(adjacency, shape, {
            'reused': 'artefact_v3.load_shape (channels, products), '
                      'artefact_v3.file_adjacency (adjacency)',
            'channels': shape['channels'], 'chunk_channel_edges': shape['chunk_channel_edges'],
            'chunks_with_channel': shape['chunks_with_channel'], 'products': shape['products'],
            'adjacent_pairs': adjacency['pairs'], 'adjacent_pairs_per_kind': adjacency['per_kind'],
            'located_chunks': adjacency['located']})
        say('artefact_v4: building the strength layer over the eligible edges')
        strength_layer = _strength_layer([dict(r) for r in chunk_rows], edge_tag, edge_chunk,
                                         edge_topic, multikey_layer.values, casefold_eligible,
                                         structure)
        strength_counts = strength_layer.source
        say(f'artefact_v4: strength layer: {strength_counts["eligible_edges"]} eligible edges on '
            f'{strength_counts["eligible_graph_tags"]} eligible graph tags; topic bulk '
            f'{strength_counts["topic_bulk"]:.4f}, spread {strength_counts["topic_spread"]:.4f}; '
            'nodes ' + ', '.join(f'{kind} {strength_counts["nodes"][kind]}'
                                 for kind in ST.STRUCTURE_TYPES))
        say('artefact_v4: building the walk layer over the eligible edges')
        same_thing = WK.same_thing_level([_readable(t) for t in graph_tags], tag_vectors,
                                         casefold_eligible)
        if same_thing is not None:
            say(f'artefact_v4: the graph\'s same-thing tag pairs ({same_thing["pairs"]}) score '
                f'{same_thing["median"]:.3f} at the median; {same_thing["point"]}% lie under '
                f'{same_thing["level"]:.4f}')
        walk_layer = _walk_layer(chunk_ids, chunk_kinds, edge_tag, edge_chunk, edge_topic,
                                 multikey_layer.values, casefold_eligible, structure,
                                 facet_gaps,
                                 same_level=None if same_thing is None else same_thing['level'])
        walk_counts = _walk_counts(walk_layer)
        say(f'artefact_v4: walk layer: {walk_counts["eligible_edges"]} eligible edges on '
            f'{walk_counts["eligible_graph_tags"]} eligible graph tags, five positions each; '
            f'{walk_counts["near_groups"]} near groups over '
            f'{walk_counts["chunks_in_a_near_group"]} chunks; {walk_counts["products"]} '
            f'products; {len(walk_counts["record_kinds"])} record kinds')
        paths = [Path(__file__), ROOT / 'test/arms/artefact_facet_joint.py',
                 ROOT / 'test/arms/artefact_v2.py', ROOT / 'test/artefact/query_content.py',
                 ROOT / 'test/artefact/querytagger.py',
                 ROOT / 'test/artefact/learned_relations.py', ROOT / 'test/artefact/landing.py',
                 ROOT / 'prod/harness/chat.py', ROOT / 'prod/harness/embed.py',
                 ROOT / 'prod/harness/char_budget.py', ROOT / 'test/artefact/v4_rank.py',
                 ROOT / 'test/artefact/v4_multikey.py', ROOT / 'test/artefact/v4_strength.py',
                 ROOT / 'test/artefact/v4_walk.py',
                 ROOT / 'test/arms/artefact_v3.py', BANDS_FILE]
        provenance = {
            'database': DATABASE, 'run_id': RUN_ID, 'corpus_argument': str(corpus),
            'interpreter_model': INTERPRET_MODEL,
            'learned_dir': str(LEARNED_DIR.relative_to(ROOT)),
            'learned_source_sha256': learned.source_sha256,
            'learned_overlay_sha256': learned.overlay_sha256,
            'facet_columns': list(POS_COLUMNS),
            'counts': {'chunks': len(chunk_ids), 'graph_tags': len(graph_tags),
                       'edges': len(learned.endpoints), 'resolved_names': len(landings),
                       'products': len(product_names), 'product_named_tags': len(product_tags),
                       'product_named_tags_casefold': int((~casefold_eligible).sum()),
                       'product_named_tags_case_variants': case_variants,
                       'chunks_without_learned_edge': edgeless,
                       'edges_with_negative_topic_cosine': negative_topic},
            'source_sha256': {str(p.relative_to(ROOT)): _sha(p.read_bytes()) for p in paths},
            'rank_layer': {'flip_gap_source': {**gap_source,
                                               'path': str(BANDS_FILE.relative_to(ROOT))},
                           **rank_layer.conversion},
            'multikey_layer': {'facet_gaps': dict(zip(R4.ADJUST_FACETS, facet_gaps)),
                               'facet_gap_source': {**facet_gap_source,
                                                    'path': str(BANDS_FILE.relative_to(ROOT))},
                               'facet_value_source': {**refit_source,
                                                      'path': str(REFITS_FILE.relative_to(ROOT))},
                               'value_columns': list(R4.ADJUST_FACETS)},
            'strength_layer': {**strength_counts,
                               'eligible': 'every graph tag except the product-name tags, '
                                           'casefolded',
                               'facet_scores': 'the multikey layer\'s values, each edge\'s mean '
                                               'over the refits, read as ranks over the '
                                               'eligible edges',
                               'file': 'the chunk\'s relpath'},
            'walk_layer': {**walk_counts, 'same_thing_pairs': same_thing,
                           'self_difference': 'measured at the first question under '
                                              'HERB_V4_WALK_RANK=picked (_walk_width), in '
                                              'that row\'s meta',
                           'eligible': 'every graph tag except the product-name tags, casefolded',
                           'facet_values': 'the multikey layer\'s values, each edge\'s mean over '
                                           'the refits, read as average ranks over the eligible '
                                           'edges',
                           'record_kind': 'the kind stored with the chunk in scores.jsonl',
                           'near_group': 'a connected component of the file adjacency with at '
                                         'least two chunks'},
            'structure': structure.source,
            'landing_corpus_words': {
                'words': len(corpus_words),
                'sha256': _sha('\n'.join(sorted(corpus_words))),
                'source': 'the pool chunks\' texts as _resolve_chunk returns them, split by '
                          'landing._tokens, casefolded'},
            'graph_writes': 0,
        }
    except BaseException:
        driver.close()
        raise
    elapsed = time.perf_counter() - started
    say(f'artefact_v4: prepared {len(chunk_ids)} chunks, {len(graph_tags)} tags, '
        f'{len(learned.endpoints)} edges, {len(product_tags)} product-named tags '
        f'in {elapsed:.1f}s')
    prepared = Prepared(tuple(dict(r) for r in chunk_rows), chunk_ids, chunk_kinds, graph_tags,
                        product_tags, nonscope_eligible, tag_vectors, chunk_vectors,
                        edge_tag, edge_chunk, edge_topic, edge_pos, landings, driver, cache,
                        provenance, BuildStats(elapsed, ModelUsage(), [INTERPRET_MODEL]),
                        rank_layer, casefold_eligible, multikey_layer, structure,
                        corpus_words, strength_layer)
    return replace(prepared, walk_layer=walk_layer)


def pick(fit, band, eligible=None):
    """Every eligible graph tag within the band of this probe's best eligible fit."""
    fit = np.asarray(fit, dtype=np.float64)
    if fit.ndim != 1 or not fit.size or not np.isfinite(fit).all():
        raise ValueError('Expected one finite fit row per graph tag')
    if eligible is None:
        return np.flatnonzero(fit >= fit.max() - band)
    eligible = np.asarray(eligible, dtype=bool)
    if eligible.shape != fit.shape:
        raise ValueError('The eligibility mask must cover every graph tag')
    if not eligible.any():
        return np.zeros(0, dtype=np.int64)
    return np.flatnonzero(eligible & (fit >= fit[eligible].max() - band))


def score(prepared, tag_probes, text_cosines, *, band, facets_on, tagside='all'):
    """The three score components, the picks, and the per-(probe, edge) adjust values.

    tag_probes: (fit row over graph tags, five readings) per tag probe.
    text_cosines: one cosine row over chunks per text probe.
    """
    if tagside not in TAGSIDE_MODES:
        raise ValueError(f'tagside must be one of {TAGSIDE_MODES}, got {tagside!r}')
    eligible = None if tagside == 'all' else prepared.nonscope_eligible
    n = len(prepared.chunk_ids)
    edge_tag, edge_chunk = prepared.edge_tag, prepared.edge_chunk
    kinds = np.asarray(prepared.chunk_kinds, dtype=object)
    tag_part = np.zeros(n)
    tag_part_plain = np.zeros(n)
    text_part = np.zeros(n)
    picked_counts, adjust_values, adjust_kinds = [], [], []
    for fit, readings in tag_probes:
        fit = np.asarray(fit, dtype=np.float64)
        readings = np.asarray(readings, dtype=np.float64)
        if readings.shape != (len(FACETS),) or not np.isfinite(readings).all():
            raise ValueError('Expected five finite facet readings per tag probe')
        chosen = pick(fit, band, eligible)
        picked_counts.append(int(chosen.size))
        keep = np.zeros(len(prepared.graph_tags), dtype=bool)
        keep[chosen] = True
        sel = np.flatnonzero(keep[edge_tag])
        if not sel.size:
            continue
        plain = fit[edge_tag[sel]] * prepared.edge_topic[sel]
        weight = readings.sum()
        if facets_on and weight > 0:
            adjust = prepared.edge_pos[sel] @ readings / weight
        else:
            adjust = np.zeros(sel.size)
        adjust_values.append(adjust)
        adjust_kinds.append(kinds[edge_chunk[sel]])
        np.add.at(tag_part, edge_chunk[sel], plain * (1. + adjust))
        np.add.at(tag_part_plain, edge_chunk[sel], plain)
    for row in text_cosines:
        row = np.asarray(row, dtype=np.float64)
        if row.shape != (n,) or not np.isfinite(row).all():
            raise ValueError('Expected one finite cosine per chunk per text probe')
        text_part = text_part + row
    return {'tag_part': tag_part, 'tag_part_plain': tag_part_plain, 'text_part': text_part,
            'picked_counts': picked_counts,
            'adjust': np.concatenate(adjust_values) if adjust_values else np.zeros(0),
            'adjust_kind': (np.concatenate(adjust_kinds) if adjust_kinds
                            else np.zeros(0, dtype=object))}


def combine_parts(parts, *, probes, facets_on):
    if probes not in PROBE_MODES:
        raise ValueError(f'probes must be one of {PROBE_MODES}, got {probes!r}')
    tag = parts['tag_part'] if facets_on else parts['tag_part_plain']
    use_tags = probes in ('all', 'tags')
    use_text = probes in ('all', 'text')
    return ((tag if use_tags else np.zeros_like(tag))
            + (parts['text_part'] if use_text else np.zeros_like(parts['text_part'])))


def _spearman(a, b):
    """Spearman's rho with average ranks for ties; None when either side is constant."""
    from scipy.stats import rankdata
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.size < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def concept_order(prepared, query_tags, d_question, d_description, *, facets_on,
                  join='adjust'):
    """Every query tag to every non-product graph tag; per query tag a chunk keeps its best
    edge by the adjusted value; the tag terms are summed over query tags and moved by the
    two text cosines."""
    if join not in JOIN_MODES:
        raise ValueError(f'join must be one of {JOIN_MODES}, got {join!r}')
    n = len(prepared.chunk_ids)
    dq = np.asarray(d_question, dtype=np.float64)
    dd = np.asarray(d_description, dtype=np.float64)
    for row in (dq, dd):
        if row.shape != (n,) or not np.isfinite(row).all():
            raise ValueError('Expected one finite description cosine per chunk')
    eligible = np.asarray(prepared.nonscope_eligible, dtype=bool)
    edge_tag, edge_chunk = prepared.edge_tag, prepared.edge_chunk
    sel = np.flatnonzero(eligible[edge_tag])
    tags_sel, chunks_sel = edge_tag[sel], edge_chunk[sel]
    columns = [FACETS.index(f) for f in ADJUST_FACETS]
    topic_sel = np.clip(prepared.edge_topic[sel], 0., None)
    pos_sel = prepared.edge_pos[sel][:, columns]
    reached = np.zeros(n, dtype=bool)
    reached[chunks_sel] = True
    terms, winners, top_tags = [], [], []
    for fit, readings in query_tags:
        fit = np.asarray(fit, dtype=np.float64)
        readings = np.asarray(readings, dtype=np.float64)
        if fit.shape != (len(prepared.graph_tags),) or not np.isfinite(fit).all():
            raise ValueError('Expected one finite fit row per graph tag')
        if readings.shape != (len(FACETS),) or not np.isfinite(readings).all():
            raise ValueError('Expected five finite facet readings per query tag')
        if facets_on:
            adjust = pos_sel @ readings[columns] / len(columns)
        else:
            adjust = np.zeros(sel.size)
        rel = np.clip(fit[tags_sel], 0., None) * topic_sel * (1. + adjust)
        term = np.full(n, -np.inf)
        np.maximum.at(term, chunks_sel, rel)
        hit = rel == term[chunks_sel]
        winner = np.full(n, len(prepared.graph_tags), dtype=np.int64)
        np.minimum.at(winner, chunks_sel[hit], tags_sel[hit])
        term[~reached] = 0.
        winner[~reached] = -1
        terms.append(term)
        winners.append(winner)
        masked = np.where(eligible, fit, -np.inf)
        top_tags.append(int(np.argmax(masked)) if eligible.any() else -1)
    tag_sum = np.sum(terms, axis=0) if terms else np.zeros(n)
    text = np.clip(dq, 0., None) + np.clip(dd, 0., None)
    if join == 'adjust':
        total = tag_sum * (1. + text)
    elif join == 'mul':
        total = tag_sum * text
    else:
        total = tag_sum + text
    ids = prepared.chunk_ids
    order = sorted(range(n), key=lambda i: (-total[i], ids[i]))
    return {'order': order, 'S': tag_sum, 'D': text, 'score': total, 'reached': reached,
            'winners': winners, 'top_tags': top_tags}


def _relative_spread(values):
    """p95 / p5 over all chunks, with both percentiles; the ratio is None when p5 is 0."""
    low, high = (float(v) for v in np.percentile(np.asarray(values, dtype=np.float64), [5, 95]))
    return {'p5': low, 'p95': high, 'p95_over_p5': (high / low) if low > 0 else None}


def concept_meta(prepared, concept, delivered):
    """What the concept sort did, with no text: S and D per credited row, the hub tags its best
    edges came through, the S-D rank agreement, and where each query tag landed."""
    degree = np.bincount(prepared.edge_tag, minlength=len(prepared.graph_tags))
    hubs_used, through_hub = set(), 0
    for c in delivered:
        hub_here = False
        for winner in concept['winners']:
            t = int(winner[c])
            if t >= 0 and degree[t] >= HUB_EDGES:
                hubs_used.add(prepared.graph_tags[t])
                hub_here = True
        through_hub += hub_here
    return {
        'query_tags': len(concept['winners']),
        'delivered_S': [float(concept['S'][c]) for c in delivered],
        'delivered_D': [float(concept['D'][c]) for c in delivered],
        'delivered_chunks_with_a_best_edge_through_a_hub_tag': through_hub,
        'hub_tags_used': sorted(hubs_used),
        'hub_edges_threshold': HUB_EDGES,
        'spearman_S_D_all_chunks': _spearman(concept['S'], concept['D']),
        'relative_spread_S_all_chunks': _relative_spread(concept['S']),
        'relative_spread_1_plus_D_all_chunks': _relative_spread(1. + concept['D']),
        'top_graph_tag_by_fit_per_query_tag': [prepared.graph_tags[t] if t >= 0 else None
                                               for t in concept['top_tags']],
        'chunks_without_an_eligible_edge': int((~concept['reached']).sum()),
    }


def best_fit_all(fits, eligible=None):
    """The highest fit of any query tag to any eligible graph tag; None when nothing is eligible."""
    best = None
    for fit in fits:
        fit = np.asarray(fit, dtype=np.float64)
        if fit.ndim != 1 or not fit.size or not np.isfinite(fit).all():
            raise ValueError('Expected one finite fit row per graph tag')
        mask = np.ones(fit.shape, dtype=bool) if eligible is None else np.asarray(eligible, bool)
        if mask.shape != fit.shape:
            raise ValueError('The eligibility mask must cover every graph tag')
        if mask.any():
            top = float(fit[mask].max())
            best = top if best is None else max(best, top)
    return best


def fit_levels(fit, best, eligible=None):
    """floor((best - fit) / COS_NOISE) per graph tag against the question's one best; -1 for none."""
    fit = np.asarray(fit, dtype=np.float64)
    if fit.ndim != 1 or not fit.size or not np.isfinite(fit).all():
        raise ValueError('Expected one finite fit row per graph tag')
    if eligible is None:
        eligible = np.ones(fit.shape, dtype=bool)
    eligible = np.asarray(eligible, dtype=bool)
    if eligible.shape != fit.shape:
        raise ValueError('The eligibility mask must cover every graph tag')
    levels = np.full(fit.shape, -1, dtype=np.int64)
    if best is not None and eligible.any():
        levels[eligible] = np.floor((best - fit[eligible]) / COS_NOISE).astype(np.int64)
    return levels


def chain_order(prepared, query_tags, description, *, facets_on, tagside='all'):
    """His chain: fit level, then facet relevance level, then the description, per chunk's best.

    query_tags: (fit row over graph tags, five readings) per query tag.
    description: cos(interpreted description, chunk description) per chunk.
    """
    if tagside not in TAGSIDE_MODES:
        raise ValueError(f'tagside must be one of {TAGSIDE_MODES}, got {tagside!r}')
    n = len(prepared.chunk_ids)
    d = np.asarray(description, dtype=np.float64)
    if d.shape != (n,) or not np.isfinite(d).all():
        raise ValueError('Expected one finite description cosine per chunk')
    eligible = None if tagside == 'all' else prepared.nonscope_eligible
    edge_tag, edge_chunk = prepared.edge_tag, prepared.edge_chunk
    tag_levels, fl_parts, rel_parts, chunk_parts, q_parts = [], [], [], [], []
    anchor_fit = best_fit_all([fit for fit, _ in query_tags], eligible)
    for qi, (fit, readings) in enumerate(query_tags):
        readings = np.asarray(readings, dtype=np.float64)
        if readings.shape != (len(FACETS),) or not np.isfinite(readings).all():
            raise ValueError('Expected five finite facet readings per query tag')
        levels = fit_levels(fit, anchor_fit, eligible)
        tag_levels.append(levels)
        sel = np.flatnonzero(levels[edge_tag] >= 0)
        weight = readings.sum()
        if facets_on and weight > 0:
            adjust = prepared.edge_pos[sel] @ readings / weight
        else:
            adjust = np.zeros(sel.size)
        fl_parts.append(levels[edge_tag[sel]])
        rel_parts.append(prepared.edge_topic[sel] * (1. + adjust))
        chunk_parts.append(edge_chunk[sel])
        q_parts.append(np.full(sel.size, qi, dtype=np.int64))
    empty_i = np.zeros(0, dtype=np.int64)
    fl = np.concatenate(fl_parts) if fl_parts else empty_i
    rel = np.concatenate(rel_parts) if rel_parts else np.zeros(0)
    chunk = np.concatenate(chunk_parts) if chunk_parts else empty_i
    qidx = np.concatenate(q_parts) if q_parts else empty_i
    if fl.size:
        top = np.full(int(fl.max()) + 1, -np.inf)
        np.maximum.at(top, fl, rel)
        rl = np.floor((top[fl] - rel) / COS_NOISE).astype(np.int64)
        base = int(rl.max()) + 1
        key = fl * base + rl
    else:
        rl, base, key = empty_i, 1, empty_i
    sentinel = np.iinfo(np.int64).max
    best = np.full(n, sentinel, dtype=np.int64)
    np.minimum.at(best, chunk, key)
    reached = best != sentinel
    at_best = key == best[chunk]
    pairs = np.unique(np.stack([chunk[at_best], qidx[at_best]]), axis=1) if at_best.any()         else np.zeros((2, 0), dtype=np.int64)
    tags_at_best = np.bincount(pairs[0], minlength=n) if pairs.size else np.zeros(n, dtype=np.int64)
    best_fl = np.where(reached, best // base, -1)
    best_rl = np.where(reached, best % base, -1)
    ids = prepared.chunk_ids
    head = sorted(np.flatnonzero(reached).tolist(), key=lambda i: (best[i], -d[i], ids[i]))
    tail = sorted(np.flatnonzero(~reached).tolist(), key=lambda i: (-d[i], ids[i]))
    return {'order': head + tail, 'reached': reached, 'best_fit_level': best_fl,
            'best_fit_all': anchor_fit, 'key_base': base, 'd': d,
            'best_rel_level': best_rl, 'query_tags_at_best_key': tags_at_best,
            'tag_levels': tag_levels, 'edge_fit_level': fl, 'edge_chunk': chunk,
            'edge_rel_level': rl}


def chain_meta(prepared, chain, delivered):
    """What the chain did up to the cut, with no text."""
    reached = chain['reached']
    bfl, brl = chain['best_fit_level'], chain['best_rel_level']
    credited_reached = [i for i in delivered if reached[i]]
    last = delivered[-1] if delivered else None
    top = max((int(bfl[i]) for i in credited_reached), default=-1)
    levels = []
    for level in range(top + 1):
        pairs = int(sum(int((lv == level).sum()) for lv in chain['tag_levels']))
        if not pairs:
            continue
        at = chain['edge_fit_level'] == level
        levels.append({'fit_level': level, 'query_tag_graph_tag_pairs': pairs,
                       'chunks_reached': int(np.unique(chain['edge_chunk'][at]).size),
                       'chunks_whose_best_is_here': int((bfl == level).sum())})
    d = chain['d']
    by_description, by_chunk_id = 0, 0
    for i, c in enumerate(delivered):
        if not reached[c]:
            continue
        tied = [o for o in (delivered[i - 1] if i > 0 else None,
                            delivered[i + 1] if i + 1 < len(delivered) else None)
                if o is not None and reached[o] and bfl[o] == bfl[c] and brl[o] == brl[c]]
        if any(d[o] != d[c] for o in tied):
            by_description += 1
        elif tied:
            by_chunk_id += 1
    level0 = set()
    for lv in chain['tag_levels']:
        level0.update(np.flatnonzero(lv == 0).tolist())
    products = set(prepared.product_tags)
    return {
        'fit_levels_opened': levels,
        'fit_level_steps_spanned': top + 1,
        'last_credited_fit_level': (int(bfl[last]) if last is not None and reached[last] else None),
        'last_credited_rel_level': (int(brl[last]) if last is not None and reached[last] else None),
        'credited_rows_decided_by_description': by_description,
        'credited_rows_decided_by_chunk_id': by_chunk_id,
        'best_fit_all': chain['best_fit_all'],
        'credited_chunks_reached_by_more_than_one_query_tag_at_best_key':
            int(sum(1 for c in credited_reached if chain['query_tags_at_best_key'][c] > 1)),
        'graph_tags_at_fit_level_0': len(level0),
        'product_named_graph_tags_at_fit_level_0':
            sum(1 for t in level0 if prepared.graph_tags[t] in products),
        'credited_unreached_rows': len(delivered) - len(credited_reached),
        'reached_chunks': int(reached.sum()),
    }


def _deciding_key(delivered, key, names):
    """For each adjacent credited pair, the name of the first key that separates them."""
    counts = {name: 0 for name in names}
    for a, b in zip(delivered, delivered[1:]):
        for name, x, y in zip(names, key(a), key(b)):
            if x != y:
                counts[name] += 1
                break
    return counts


def adjust_lower_meta(lower, tag_score, reached, text_cosines, area_rank, delivered, descjoin):
    """What the adjust_lower sort did up to the cut, with no text."""
    dd, dq = text_cosines['description'], text_cosines['question']
    score = lower['score']
    if descjoin == 'key':
        ld, lq = R4.levels(dd, R4.COS_NOISE), R4.levels(dq, R4.COS_NOISE)
        names = ('reached', 'score', 'description_level', 'question_level', 'landing',
                 'chunk_id')
        key = lambda i: (not reached[i], -score[i], ld[i], lq[i], area_rank[i], i)
    else:
        names = ('reached', 'score', 'landing', 'chunk_id')
        key = lambda i: (not reached[i], -score[i], area_rank[i], i)
    return {
        'delivered_tag_score': [float(tag_score[i]) for i in delivered],
        'delivered_description_cosines': [float(dd[i]) for i in delivered],
        'delivered_question_cosines': [float(dq[i]) for i in delivered],
        'credited_rows_in_landing_meet': int(sum(1 for i in delivered if area_rank[i] == 0)),
        'adjacent_credited_pairs_separated_by': _deciding_key(delivered, key, names),
        'chunks_reached_by_a_non_product_edge': int(reached.sum()),
    }


def multirank_meta(multi, text_cosines, area_rank, delivered):
    """What the multirank sort did up to the cut, with no text."""
    ld = R4.levels(text_cosines['description'], R4.COS_NOISE)
    lq = R4.levels(text_cosines['question'], R4.COS_NOISE)
    reached, fl, levels, columns = (multi['reached'], multi['fit_level'], multi['edge_levels'],
                                    multi['columns'])
    names = ('reached', 'strength_level', 'column_1', 'column_2', 'column_3', 'column_4', 'column_5',
             'description_level', 'question_level', 'landing', 'chunk_id')

    def key(i):
        if not reached[i]:
            return (1, -1, -1, -1, -1, -1, -1, ld[i], lq[i], area_rank[i], i)
        return (0, fl[i], *(levels[i, j] for j in columns[i]), ld[i], lq[i], area_rank[i], i)

    return {
        'best_strength_all': multi['best_strength_all'],
        'credited_rows_in_landing_meet': int(sum(1 for i in delivered if area_rank[i] == 0)),
        'adjacent_credited_pairs_separated_by': _deciding_key(delivered, key, names),
        'credited_unreached_rows': int(sum(1 for i in delivered if not reached[i])),
        'first_column_of_credited_rows': {
            f: int(sum(1 for i in delivered if reached[i] and R4.ALL_FACETS[columns[i][0]] == f))
            for f in R4.ALL_FACETS},
        'chunks_reached_by_a_non_product_edge': int(reached.sum()),
    }


def multikey_meta(multi, delivered):
    """What the multikey sort did up to the cut, with no text: for the adjacent pairs among the
    first DECIDER_WINDOW credited rows, the first key that separates the two."""
    keys = multi['keys']
    window = list(delivered[:DECIDER_WINDOW])
    meta = {
        'key_names': list(multi['key_names']),
        'best_fit_all': multi['fit_best'],
        'best_topic_over_the_question_edges': multi['topic_best'],
        'best_score_per_facet_over_the_question_edges': multi['facet_column_best'],
        'edges_sorted': multi['edges_sorted'],
        'chunks_reached_by_a_non_product_edge': int(multi['reached'].sum()),
        'credited_unreached_rows': int(sum(1 for i in delivered if not multi['reached'][i])),
        'seeds': multi['seeds'],
        'decider_window_rows': len(window),
        'adjacent_pairs_in_the_window': max(len(window) - 1, 0),
        'adjacent_pairs_in_the_window_separated_by': _deciding_key(
            window, lambda i: tuple(int(v) for v in keys[i]), multi['key_names']),
    }
    if 'landed_chunks' in multi:
        meta['landed_chunks'] = multi['landed_chunks']
        meta['seed_distance_histogram'] = multi['seed_distance_histogram']
    return meta


# Per text switch of `v4_walk.chain` the texts whose standing enters the strength.
WALK_TEXTS = {'max': ('description', 'question'), 'clipped': ('description', 'question'),
              'description': ('description',), 'none': ()}
# Per switch value of `v4_walk.chain` what the run leaves unread.
WALK_NOT_READ = {
    ('share', 'equal'): 'the query tag\'s readings as shares: every query tag takes five equal '
                        'shares; the readings still give the facet order inside a level',
    ('share', 'none'): 'the shares and the edge\'s positions in the weight: w = fit; inside a '
                       'level the winning edge\'s four facet positions still order',
    ('central', 'equal'): 'the query tags\' cosines to the query description: every query tag '
                          'weighs 1',
    ('chunk', 'none'): 'the tags: T = 0 for every chunk; the query tags\' bulk, spread, '
                       'centrality and shares are computed and not read; the level step '
                       'reads the spreads of the texts in the side',
    ('side', 'none'): 'the description and the raw question: S = T',
    ('side', 'description'): 'the raw question: the side is D alone',
    ('structure', 'none'): 'the structure: S\' = S',
    ('order', 'plain'): 'the levels: the rows are ordered by S\' descending, then chunk id; the '
                        'level numbers under the unused_ names did not order them',
}


def walk_terms(walked, switches):
    """The terms that add up to a chunk's strength under the walk sort: T, the side unless the
    run reads no text, and each grouping's lift."""
    terms = {'tags': walked['T']}
    if WALK_TEXTS[switches.get('side', 'max')]:
        terms['description'] = walked['side']
    return {**terms, **walked['lift']}


def walk_winners(walked, rows):
    """Per row the winning query tag; -1 for a chunk with no eligible edge and for a chunk
    whose T is 0, where no pair gave a value above 0."""
    return [int(walked['winner'][i]) if walked['has_edge'][i] and walked['T'][i] != 0. else -1
            for i in rows]


def walk_meta(layer, walked, delivered, switches):
    """What the walk sort did up to the cut, with no text: the counts, each query tag's bulk,
    spread and centrality, per grouping the groups, the two variances and the lifts, and over
    the credited rows each term's sum and its share of their total strength, the rows whose Qs
    stands above their D, and the levels. switches: the switches of `v4_walk.chain` the run
    set. What they leave unread is None or absent and named under `not_read`: the text bulk,
    spread and Qs-above-D count follow the texts that enter the strength; the query tags with
    equal shares are those whose readings summed to 0, all of them under equal shares, None
    with the shares off; with no levels ordering the rows the level numbers the chain still
    computes stand under `unused_` names."""
    delivered = [int(i) for i in delivered]
    count = int(walked['bulk'].size)
    texts = WALK_TEXTS[switches.get('side', 'max')]
    by_levels = switches.get('order', 'levels') == 'levels'
    terms = walk_terms(walked, switches)
    sums = {name: float(values[delivered].sum()) for name, values in terms.items()}
    total = float(walked['S_prime'][delivered].sum())
    levels = walked['level'][delivered]
    level_numbers = {
        'level_step': float(walked['step']),
        'levels_among_delivered_rows': int(np.unique(levels).size),
        'adjacent_delivered_pairs_in_one_level': int((levels[1:] == levels[:-1]).sum())}
    return {
        'chunks': int(layer['chunks']),
        'eligible_graph_tags': int(layer['eligible'].sum()),
        'eligible_edges': int(layer['edges'].size),
        'chunks_with_an_eligible_edge': int((layer['n_c'] > 0).sum()),
        'chunks_with_a_positive_tag_strength': int((walked['T'] > 0).sum()),
        'query_tags': count,
        'query_tags_with_equal_shares': {
            'readings': int(walked['equal_shares'].sum()), 'equal': count,
            'none': None}[switches.get('share', 'readings')],
        'query_tag_bulk': walked['bulk'].tolist(),
        'query_tag_spread': walked['spread'].tolist(),
        'query_tag_centrality': walked['centrality'].tolist(),
        'rank': (None if walked.get('edge_class') is None else {
            'equal_width_per_query_tag': walked['rank_width'].tolist(),
            'equal_share_of_the_closest': (WK.EQUAL_SHARE
                                           if switches.get('rank') == 'percent' else None),
            'same_thing_level': (layer.get('same_level')
                                 if switches.get('rank') == 'same' else None),
            'self_difference': (layer.get('self_difference_measured')
                                if switches.get('rank') == 'picked' else None),
            'picked_edges_per_query_tag': (walked['edge_class'] == 0).sum(axis=1).tolist(),
            'delivered_winning_edge_class': [
                (int(walked['edge_class'][walked['winner'][c], walked['win_edge'][c]])
                 if walked['win_edge'][c] >= 0 and walked['T'][c] > 0 else None)
                for c in delivered],
            'delivered_winning_edge_place': [
                (int(walked['edge_place'][walked['winner'][c], walked['win_edge'][c]])
                 if walked['win_edge'][c] >= 0 and walked['T'][c] > 0 else None)
                for c in delivered]}),
        'texts_in_the_strength': list(texts),
        'text_bulk': {name: walked['text_bulk'][name] for name in texts} or None,
        'text_spread': {name: walked['text_spread'][name] for name in texts} or None,
        'groupings': {kind: {'groups': int(part['groups']),
                             'memberships': int(part['memberships']),
                             'sigma2': part['sigma2'], 'tau2': part['tau2'],
                             'chunks_with_a_lift_above_0': int((part['lift'] > 0).sum()),
                             'largest_lift': float(part['lift'].max())}
                      for kind, part in walked['groups'].items()},
        'delivered_term_sums': sums,
        'delivered_strength_total': total,
        'delivered_term_shares': {name: (sums[name] / total if total != 0. else None)
                                  for name in sums},
        'delivered_rows_with_Qs_above_D': (
            int((walked['Qs'][delivered] > walked['D'][delivered]).sum())
            if len(texts) == 2 else None),
        'adjacent_delivered_pairs': max(len(delivered) - 1, 0),
        'levels_order_the_rows': by_levels,
        **(level_numbers if by_levels
           else {'unused_' + name: value for name, value in level_numbers.items()}),
        'not_read': [text for item, text in WALK_NOT_READ.items() if item in switches.items()],
    }


def order_keys(chunk_ids, total, area_rank):
    return sorted(range(len(chunk_ids)),
                  key=lambda i: (area_rank[i], -total[i], chunk_ids[i]))


def _flip_fraction(delivered, alt, area_rank):
    """Adjacent delivered pairs the alternative score strictly reverses; a tie is no flip."""
    if len(delivered) < 2:
        return None
    flips = 0
    for a, b in zip(delivered, delivered[1:]):
        if (area_rank[b], -alt[b]) < (area_rank[a], -alt[a]):
            flips += 1
    return flips / (len(delivered) - 1)


def _eta_squared(values, groups):
    """Share of the adjust's variance between record kinds; None when it has none."""
    if values.size < 2:
        return None
    grand = values.mean()
    total = float(((values - grand) ** 2).sum())
    if total == 0.:
        return None
    between = 0.
    for name in set(groups.tolist()):
        member = values[groups == name]
        between += member.size * (member.mean() - grand) ** 2
    return float(between / total)


def _area_rank(prepared, text, mode):
    """The meet of the question's landings; no name means no area.

    first: every landing `landing.land` reads enters the meet. landed (the multikey structure
    key): a capitalised word the corpus carries never reaches the nearest-name pass, and a
    landing whose nodes reach no chunk is dropped from the meet and recorded (both the
    orchestrator's constructions); no landing left means no area."""
    if mode == 'off':
        return np.zeros(len(prepared.chunk_ids), dtype=np.int64), {'mode': 'off'}
    if mode == 'landed':
        if prepared.corpus_words is None:
            raise ValueError('The landed area needs the prepared corpus words')
        hits = LAND.land(text, list(prepared.landings), known=prepared.corpus_words)
    else:
        hits = LAND.land(text, list(prepared.landings))
    with prepared.driver.session(database=DATABASE, default_access_mode='READ') as session:
        reached = LAND.areas(session, hits)
    area = (LAND.combine(reached, hits, drop_empty=True) if mode == 'landed'
            else LAND.combine(reached, hits))
    rank = np.zeros(len(prepared.chunk_ids), dtype=np.int64)
    meta = {'mode': mode, 'hits': len(hits), 'landed_nodes': len(reached.by_node),
            'reached_chunks': len(reached.by_chunk)}
    if mode == 'landed':
        meta['rules'] = {'nearest_name_pass': 'only for windows holding a word the corpus '
                                              'does not carry',
                         'landing_with_no_chunk': 'dropped from the meet'}
        meta['dropped'] = [f'{kind}:{name}' for kind, name in (area.dropped if area else ())]
    if area is None or not area.landings:
        meta['area'] = None
        return rank, meta
    meta['landings'] = {f'{kind}:{name}': len(chunks)
                        for (kind, name), chunks in area.landings.items()}
    meta['unmet'] = [f'{kind}:{name}' for kind, name in area.unmet]
    inside = area.chunks
    rank = np.array([0 if cid in inside else 1 for cid in prepared.chunk_ids], dtype=np.int64)
    meta['area'] = int((rank == 0).sum())
    return rank, meta


def _collapse_duplicate_tags(raw):
    """The querytagger sometimes writes one tag twice in a list; the first stays, the rest are
    dropped and counted, so a repeated phrase does not fail the question for good in the cache.
    Each list (tags, query_tags) is collapsed on its own."""
    if not isinstance(raw, dict) or not isinstance(raw.get('tags'), list):
        return raw, 0
    out, dropped = dict(raw), 0
    for field in ('tags', 'query_tags'):
        if not isinstance(raw.get(field), list):
            continue
        kept, seen = [], set()
        for row in raw[field]:
            name = row.get('t') if isinstance(row, dict) else None
            key = name.strip().casefold() if isinstance(name, str) else None
            if key is not None and key in seen:
                dropped += 1
                continue
            if key is not None:
                seen.add(key)
            kept.append(row)
        out[field] = kept
    return out, dropped


def _require_cached_answer(system, user, cache_dir):
    """Under HERB_V4_OFFLINE=on the querytagger answer must already sit in the cache as a good
    answer under the key `_cached_stage` reads; anything else raises before any model call."""
    signature = {'cache_version': 1, 'stage': 'querytag', 'model': INTERPRET_MODEL,
                 'system': system, 'user': user, 'max_tries': 1}
    key = _sha(json.dumps(signature, sort_keys=True, ensure_ascii=False))
    path = Path(cache_dir) / 'querytag' / (key + '.json')
    if not path.is_file():
        raise RuntimeError('artefact_v4: HERB_V4_OFFLINE=on and no cached querytagger answer '
                           f'(key {key}); no model call made')
    saved = json.loads(path.read_text(encoding='utf-8'))
    if not saved.get('ok') or saved.get('signature') != signature:
        raise RuntimeError('artefact_v4: HERB_V4_OFFLINE=on and the cached querytagger answer '
                           f'is not a good answer (key {key}); no model call made')
    return key


def _interpret(text, prepared):
    """One querytagger call: the question in; the description, the tags and each tag's five
    readings out (his 2026-09-26 "dont do 3 different calls"). Under HERB_V4_OFFLINE=on only a
    good cached answer is read, and no model is ever asked."""
    usage = ModelUsage()
    system, user = Q.request(text)
    offline = knobs()['offline'] == 'on'
    offline_key = _require_cached_answer(system, user, prepared.cache_dir) if offline else None
    dropped = []

    def validate(raw):
        cleaned, n = _collapse_duplicate_tags(raw)
        dropped.append(n)
        return Q.parse(text, cleaned)

    tries = 0
    while True:
        tries += 1
        try:
            value, used, cache = _cached_stage('querytag', system, user, validate,
                                               prepared.cache_dir)
            break
        except RuntimeError as failure:
            # The transport caches a failed answer (no JSON, a refusal) for good. One
            # re-ask: the cached failure is removed and the question asked again once.
            if offline or tries >= 2:
                raise
            key = str(failure).split('key=')[-1].split(';')[0].strip()
            path = Path(prepared.cache_dir) / 'querytag' / (key + '.json')
            marker = path.with_suffix('.started.json')
            own_attempt = 'no retry' in str(failure)
            if not own_attempt or not path.exists():
                raise  # a marker or a failure this process did not write is left as it is
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('ok'):
                raise  # a good answer the arm's own validation rejected: not a re-ask case
            path.unlink()
            if marker.exists():
                marker.unlink()
            say(f'artefact_v4: querytagger answer unusable ({failure}); asking once more')
    if offline and (not cache['cache_hit'] or cache['key'] != offline_key or used.calls):
        raise RuntimeError('artefact_v4: HERB_V4_OFFLINE=on and the querytagger answer was not '
                           'the cached one')
    for name in ModelUsage.__dataclass_fields__:
        setattr(usage, name, getattr(usage, name) + getattr(used, name))
    stages = [{'stage': 'querytag', 'cache_hit': cache['cache_hit'], 'key': cache['key'],
               'asks': tries, 'offline': offline,
               'duplicate_tags_dropped': dropped[-1] if dropped else None}]
    return value, usage, stages


@dataclass(frozen=True)
class _QueryAxes:
    tag_vectors: np.ndarray
    chunk_vectors: np.ndarray


def _query_cosines_and_centrality(description, tags, prepared, role='query'):
    """`_query_cosines`' fits and description cosines and, from the same embedding call, each
    tag's cosine to the description; the call is in the query role unless another is named.
    `_query_cosines` multiplies its unit query vectors with the chunk matrix it is handed;
    handed the identity it returns the vectors themselves, and the cosines to the chunk
    descriptions and to the description are taken from them here."""
    dim = prepared.chunk_vectors.shape[1]
    matrices, used, recipe = _query_cosines(
        description, tags, _QueryAxes(prepared.tag_vectors, np.eye(dim)),
        *(() if role == 'query' else (role,)))
    tag_vectors = np.asarray(matrices['query_chunk_cosines'], dtype=np.float64)
    description_vector = np.asarray(matrices['query_description_cosines'], dtype=np.float64)
    if tag_vectors.shape != (len(tags), dim) or description_vector.shape != (dim,):
        raise ValueError('Expected one query vector per tag and one for the description')
    return ({'query_tag_cosines': matrices['query_tag_cosines'],
             'query_description_cosines': description_vector @ prepared.chunk_vectors.T,
             'query_tag_description_cosines': tag_vectors @ description_vector}, used, recipe)


def _walk_cosines(description, tags, prepared, roles):
    """One tag list's cosines for the walk sort, each comparison embedded in its role
    (`walk_roles`). The tags and the description are embedded together in the centrality's
    role: each tag's cosine to the description comes from that call. Where the tags' role is
    another, the tags are embedded once more, alone and in their role, for their cosines to the
    graph tags; where the description's role is another, the description is embedded once more,
    alone and in its role, for its cosines to the chunk descriptions. Returns the three
    matrices of `_query_cosines_and_centrality`, the usage of every call, and the vector sha256
    of the call the tags' cosines to the graph tags come from, with every call's by role."""
    central = roles['centrality']
    matrices, used, recipe = _query_cosines_and_centrality(description, tags, prepared, central)
    matrices = dict(matrices)
    by_role = {central: recipe['vector_sha256']}
    if roles['tags'] != central and tags:
        alone, more, recipe = _query_cosines(tags[0], tags, prepared, roles['tags'])
        matrices['query_tag_cosines'] = alone['query_tag_cosines']
        by_role[roles['tags']] = recipe['vector_sha256']
        used = ModelUsage(**{name: getattr(used, name) + getattr(more, name)
                             for name in ModelUsage.__dataclass_fields__})
    if roles['description'] != central:
        alone, more, recipe = _query_cosines(description, [], prepared, roles['description'])
        matrices['query_description_cosines'] = alone['query_description_cosines']
        by_role[roles['description']] = recipe['vector_sha256']
        used = ModelUsage(**{name: getattr(used, name) + getattr(more, name)
                             for name in ModelUsage.__dataclass_fields__})
    return matrices, used, {'vector_sha256': by_role[roles['tags'] if tags else central],
                            'vector_sha256_by_role': by_role}


def answer_one_question(question, prepared: Prepared, generate, k: int = 50,
                        char_budget: int | None = None) -> ArmOutput:
    if not isinstance(question, (tuple, list)) or len(question) != 2:
        raise ValueError('Expected (question_id, raw_question)')
    qid, text = question
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Raw question must be nonempty text')
    if type(k) is not int or k < 1:
        raise ValueError('k must be a positive integer')
    if char_budget is not None and (type(char_budget) is not int or char_budget < 1):
        raise ValueError('char_budget must be a positive integer or None')
    flags = knobs()
    if flags['sort'] == 'walk' and flags['walkrank'] == 'picked':  # percent measures nothing
        if flags['walktagrole'] != 'passage':
            raise ValueError('HERB_V4_WALK_RANK=picked needs HERB_V4_WALK_TAGROLE=passage: the '
                             'self-difference is measured in the passage role')
        _walk_width(prepared)
    started = time.perf_counter()
    chat.reset_timing()
    band = BANDS[flags['band']]
    facets_on = flags['facets'] == 'on'
    query, interp_usage, stages = _interpret(text, prepared)
    for stage in stages:
        say(f'artefact_v4: {qid} {stage["stage"]} cache_hit={stage["cache_hit"]} '
            f'asks={stage["asks"]} offline={stage["offline"]}')
    embed_usage = ModelUsage()
    query_tags, text_cosines, branch_meta = [], {}, {}
    tags = [t.text for t in query.tags]
    # The description is embedded with the description-side tags (their fits and the
    # description's cosines to the chunk descriptions); the question text alone after (under
    # walk in the role its knob says); under strength, multikey, adjust_lower and walk the question-side tags
    # last, embedded beside the description. Under strength and walk each tag call also hands
    # each tag's cosine to the description. Under walk each comparison is embedded in its role
    # (`_walk_cosines`); every other sort embeds in the query role.
    by_strength = flags['sort'] == 'strength'
    by_walk = flags['sort'] == 'walk'
    with_centrality = by_strength or by_walk
    roles = walk_roles(flags) if by_walk else None
    if by_walk:
        def tag_cosines(description, listed, prepared_):
            return _walk_cosines(description, listed, prepared_, roles)
    else:
        tag_cosines = _query_cosines_and_centrality if with_centrality else _query_cosines
    centrality_cosines = []
    matrices, used, recipe = tag_cosines(query.description, tags, prepared)
    for name in ModelUsage.__dataclass_fields__:
        setattr(embed_usage, name, getattr(embed_usage, name) + getattr(used, name))
    fits = np.asarray(matrices['query_tag_cosines'], dtype=np.float64)
    for i, tag in enumerate(query.tags):
        query_tags.append((fits[i], tag.readings))
    if with_centrality:
        centrality_cosines.extend(np.asarray(matrices['query_tag_description_cosines'],
                                             dtype=np.float64).tolist())
    text_cosines['description'] = np.asarray(matrices['query_description_cosines'],
                                             dtype=np.float64)
    branch_meta['description'] = {'tags': len(tags), 'text_chars': len(query.description),
                                  'embedding': recipe['vector_sha256']}
    if by_walk:
        branch_meta['description']['embedding_by_role'] = recipe['vector_sha256_by_role']
    if by_walk and roles['question'] != 'query':
        matrices, used, recipe = _query_cosines(query.question, [], prepared, roles['question'])
    else:
        matrices, used, recipe = _query_cosines(query.question, [], prepared)
    for name in ModelUsage.__dataclass_fields__:
        setattr(embed_usage, name, getattr(embed_usage, name) + getattr(used, name))
    text_cosines['question'] = np.asarray(matrices['query_description_cosines'],
                                          dtype=np.float64)
    branch_meta['question'] = {'tags': 0, 'text_chars': len(query.question),
                               'embedding': recipe['vector_sha256']}
    question_side = ([t.text for t in query.query_tags]
                     if flags['sort'] in ('strength', 'multikey', 'adjust_lower', 'walk') else [])
    if question_side:
        matrices, used, recipe = tag_cosines(query.description, question_side, prepared)
        for name in ModelUsage.__dataclass_fields__:
            setattr(embed_usage, name, getattr(embed_usage, name) + getattr(used, name))
        fits = np.asarray(matrices['query_tag_cosines'], dtype=np.float64)
        for i, tag in enumerate(query.query_tags):
            query_tags.append((fits[i], tag.readings))
        if with_centrality:
            centrality_cosines.extend(np.asarray(matrices['query_tag_description_cosines'],
                                                 dtype=np.float64).tolist())
        branch_meta['question_side_tags'] = {'tags': len(question_side),
                                             'embedding': recipe['vector_sha256']}
        if by_walk:
            branch_meta['question_side_tags']['embedding_by_role'] = recipe[
                'vector_sha256_by_role']
    eligible = (prepared.casefold_eligible if prepared.casefold_eligible is not None
                else prepared.nonscope_eligible)
    if by_strength:
        if prepared.strength_layer is None:
            raise ValueError('strength needs the prepared strength layer')
        eligible = prepared.strength_layer.eligible
        strong = ST.strength_order(prepared.chunk_ids, prepared.strength_layer, query_tags,
                                   centrality_cosines, text_cosines['description'],
                                   text_cosines['question'])
        order = strong['order']
    elif by_walk:
        if prepared.walk_layer is None:
            raise ValueError('walk needs the prepared walk layer')
        if list(prepared.chunk_ids) != prepared.walk_layer['chunk_ids']:
            raise ValueError('Expected the walk layer over the same chunks')
        eligible = prepared.walk_layer['eligible']
        switches, selected = walk_switches(flags)
        walked = WK.chain(
            prepared.walk_layer,
            {'cosines': np.array([row for row, _ in query_tags], dtype=np.float64),
             'readings': np.array([readings for _, readings in query_tags], dtype=np.float64),
             'description_cosines': np.array(centrality_cosines, dtype=np.float64),
             'd_description': text_cosines['description'],
             'd_question': text_cosines['question']},
            COS_NOISE, **switches)
        order = walked['order']
    elif flags['sort'] == 'multikey':
        if prepared.multikey_layer is None:
            raise ValueError('multikey needs the prepared multikey layer')
        if flags['structat'] == 'off':
            landed = structure = None
            area_meta = {'mode': 'not read (HERB_V4_STRUCT_AT=off)'}
        else:
            if prepared.structure is None:
                raise ValueError('the multikey structure keys need the prepared structure')
            landed, area_meta = _area_rank(prepared, text, 'landed')
            structure = prepared.structure
        multi = MK.multikey_order(prepared.chunk_ids, prepared.edge_tag, prepared.edge_chunk,
                                  prepared.edge_topic, prepared.multikey_layer, eligible,
                                  query_tags, text_cosines['description'],
                                  text_cosines['question'], fit_step=BANDS[flags['fiteq']],
                                  landed=landed, structure=structure,
                                  struct_at=flags['structat'] if structure is not None else None)
        order = multi['order']
    elif flags['sort'] in ('adjust_lower', 'multirank'):
        layer = prepared.rank_layer
        if layer is None:
            raise ValueError('adjust_lower and multirank need the prepared rank layer')
        rank, area_meta = _area_rank(prepared, text, 'first')
        n = len(prepared.chunk_ids)
        if flags['sort'] == 'adjust_lower':
            tag_score, reached, score_stats = R4.adjust_lower_scores(
                prepared.edge_tag, prepared.edge_chunk, prepared.edge_topic, layer.pct,
                eligible, query_tags, n, qtopic=flags['qtopic'],
                edgecomb=flags['edgecomb'], facets_on=facets_on)
            lower = R4.adjust_lower_order(prepared.chunk_ids, tag_score, reached,
                                          text_cosines['description'], text_cosines['question'],
                                          rank, descjoin=flags['descjoin'])
            order = lower['order']
        else:
            multi = R4.multirank_order(prepared.chunk_ids, prepared.edge_tag, prepared.edge_chunk,
                                       prepared.edge_topic, layer, eligible,
                                       query_tags, text_cosines['description'],
                                       text_cosines['question'], rank)
            order = multi['order']
    elif flags['sort'] == 'concept':
        concept = concept_order(prepared, query_tags, text_cosines['question'],
                                text_cosines['description'], facets_on=facets_on,
                                join=flags['join'])
        order = concept['order']
    elif flags['sort'] == 'chain':
        chain = chain_order(prepared, query_tags, text_cosines['description'],
                            facets_on=facets_on, tagside=flags['tagside'])
        order = chain['order']
    else:
        parts = score(prepared, query_tags, list(text_cosines.values()), band=band,
                      facets_on=facets_on, tagside=flags['tagside'])
        total = combine_parts(parts, probes=flags['probes'], facets_on=facets_on)
        rank, area_meta = _area_rank(prepared, text, flags['area'])
        order = order_keys(prepared.chunk_ids, total, rank)
    ordered_rows = [prepared.chunk_rows[i] for i in order]
    doc_cache = {}
    if char_budget is not None:
        contexts, id_lists, context_ids, budget = _budget_contexts(ordered_rows, char_budget, doc_cache)
        credited = int(budget['kept'])
        boundary = budget['boundary']['id'] if budget['boundary'] else None
    else:
        contexts, id_lists, context_ids, budget = [], [], [], None
        for row in ordered_rows[:k]:
            content, ids = _resolve_chunk(row, doc_cache)
            contexts.append(content)
            id_lists.append(ids)
            for aid in ids:
                if aid not in context_ids:
                    context_ids.append(aid)
        credited, boundary = len(contexts), None
    delivered = order[:credited]
    diagnostics = {'credited_delivered_rows': len(delivered),
                   'boundary_chunk_id_not_credited': boundary}
    if by_strength:
        diagnostics.update(ST.summary(strong, delivered))
        diagnostics['product_named_tags_excluded_casefold'] = int((~eligible).sum())
        term_shares = diagnostics['delivered_term_shares']
        say(f'artefact_v4 strength {qid}: {len(delivered)} credited rows, strength total '
            f'{diagnostics["delivered_strength_total"]:.3f}; shares '
            + ', '.join(f'{name} ' + ('none' if term_shares[name] is None
                                      else f'{term_shares[name]:.3f}') for name in ST.TERMS)
            + f'; rows taking D {diagnostics["delivered_rows_taking_the_description"]}, Q '
            f'{diagnostics["delivered_rows_taking_the_question"]}')
        say(f'artefact_v4 strength {qid}: levels among the credited rows '
            f'{diagnostics["levels_among_delivered_rows"]}, adjacent pairs in one level '
            f'{diagnostics["adjacent_delivered_pairs_in_one_level"]} of '
            f'{diagnostics["adjacent_delivered_pairs"]}, step {diagnostics["level_step"]:.4f}; '
            'largest difference per adjacent pair: '
            + ', '.join(f'{name} {count}' for name, count in diagnostics[
                'adjacent_delivered_pairs_largest_difference_in'].items()))
        say(f'artefact_v4 strength {qid}: largest boost '
            + ', '.join(f'{kind} {diagnostics["largest_boost"][kind]:.3f}'
                        for kind in ST.STRUCTURE_TYPES)
            + '; chunks with a positive boost '
            + ', '.join(f'{kind} {diagnostics["chunks_with_a_positive_boost"][kind]}'
                        for kind in ST.STRUCTURE_TYPES)
            + f'; query tags {diagnostics["query_tags"]}, equal shares on '
            f'{diagnostics["query_tags_with_equal_shares"]}')
        terms = {'tags': strong['tags'], 'description': strong['description_side'],
                 **strong['boosts']}
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_strength': [float(strong['strength'][i]) for i in delivered],
                   'delivered_levels': [int(strong['level'][i]) for i in delivered],
                   'delivered_terms': {name: [float(terms[name][i]) for i in delivered]
                                       for name in ST.TERMS},
                   'delivered_query_tags': [int(strong['best_query_tag'][i])
                                            for i in delivered]}
        area_meta = {'mode': 'not read by the strength sort'}
        picked = None
    elif by_walk:
        diagnostics.update(walk_meta(prepared.walk_layer, walked, delivered, switches))
        diagnostics['query_tag_description_cosine'] = (
            [float(v) for v in centrality_cosines]
            if switches.get('central', 'description') == 'description' else None)
        diagnostics['phrases_standing_in_both_tag_lists'] = len(
            {t.strip().casefold() for t in tags}
            & {t.strip().casefold() for t in question_side})
        diagnostics['product_named_tags_excluded_casefold'] = int((~eligible).sum())
        diagnostics['chain_switches'] = dict(switches)
        diagnostics['alternatives_selected'] = dict(selected)
        diagnostics['embedding_roles'] = dict(roles)
        by_levels = diagnostics['levels_order_the_rows']
        qs_above = diagnostics['delivered_rows_with_Qs_above_D']
        equal_shares = diagnostics['query_tags_with_equal_shares']
        say(f'artefact_v4 walk {qid}: {len(delivered)} credited rows, strength total '
            f'{diagnostics["delivered_strength_total"]:.3f}; shares '
            + ', '.join(f'{name} ' + ('none' if share is None else f'{share:.3f}')
                        for name, share in diagnostics['delivered_term_shares'].items())
            + '; texts in the strength '
            + (', '.join(diagnostics['texts_in_the_strength']) or 'none')
            + ('' if qs_above is None else f', rows with Qs above D {qs_above}')
            + (f'; levels {diagnostics["levels_among_delivered_rows"]}, adjacent pairs in one '
               f'level {diagnostics["adjacent_delivered_pairs_in_one_level"]} of '
               f'{diagnostics["adjacent_delivered_pairs"]}, step '
               f'{diagnostics["level_step"]:.4f}' if by_levels
               else '; no levels order the rows: S\' descending, then chunk id'))
        say(f'artefact_v4 walk {qid}: '
            + (''.join(f'{kind}: {group["groups"]} groups, tau2 '
                       + ('none' if group['tau2'] is None else f'{group["tau2"]:.4f}')
                       + f', chunks lifted {group["chunks_with_a_lift_above_0"]}, largest lift '
                       f'{group["largest_lift"]:.3f}; '
                       for kind, group in diagnostics['groupings'].items())
               or 'no structure read; ')
            + f'query tags {diagnostics["query_tags"]}, '
            + ('shares not read' if equal_shares is None
               else f'equal shares on {equal_shares}')
            + f', phrases in both lists {diagnostics["phrases_standing_in_both_tag_lists"]}; '
            'alternatives '
            + (', '.join(f'{env} {alternative}' for env, alternative in selected.items())
               or 'none, the PROPOSAL')
            + '; embedding roles '
            + ', '.join(f'{name} {role}' for name, role in roles.items()))
        terms = walk_terms(walked, switches)
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_strength': [float(walked['S_prime'][i]) for i in delivered],
                   ('delivered_levels' if by_levels else 'delivered_unused_levels'): [
                       int(walked['level'][i]) for i in delivered],
                   'delivered_terms': {name: [float(values[i]) for i in delivered]
                                       for name, values in terms.items()},
                   'delivered_query_tags': walk_winners(walked, delivered)}
        area_meta = {'mode': 'not read by the walk sort'}
        picked = None
    elif flags['sort'] == 'multikey':
        diagnostics.update(multikey_meta(multi, delivered))
        diagnostics['product_named_tags_excluded_casefold'] = int((~eligible).sum())
        diagnostics['struct_at'] = flags['structat']
        say(f'artefact_v4 multikey {qid}: {diagnostics["adjacent_pairs_in_the_window"]} adjacent '
            f'pairs in the first {diagnostics["decider_window_rows"]} credited rows, separated by '
            + ', '.join(f'{name} {count}' for name, count
                        in diagnostics['adjacent_pairs_in_the_window_separated_by'].items()))
        if landed is None:
            say(f'artefact_v4 multikey {qid}: structure keys off; seeds {diagnostics["seeds"]}')
        else:
            diagnostics['landing_inert'] = bool((landed == landed[0]).all())
            diagnostics['landing_kinds_kept'] = sorted(
                key.split(':', 1)[0] for key in area_meta.get('landings', {}))
            diagnostics['landing_kinds_dropped'] = sorted(
                key.split(':', 1)[0] for key in area_meta.get('dropped', []))
            histogram = diagnostics['seed_distance_histogram']
            say(f'artefact_v4 multikey {qid}: landings kept '
                f'{len(diagnostics["landing_kinds_kept"])} '
                f'{diagnostics["landing_kinds_kept"]}, dropped '
                f'{len(diagnostics["landing_kinds_dropped"])} '
                f'{diagnostics["landing_kinds_dropped"]}; landed area {area_meta.get("area")} '
                f'chunks (key inert {diagnostics["landing_inert"]}); seeds '
                f'{diagnostics["seeds"]}; seed distance '
                + ', '.join(f'{d}: {histogram[d]}' for d in sorted(histogram)))
        sides = ['description'] * len(tags) + ['question'] * len(question_side)
        names = tags + question_side
        facet_columns = [R4.ALL_FACETS.index(f) for f in R4.ADJUST_FACETS]
        best_edge = multi['best_edge']
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'key_names': list(multi['key_names']),
                   'delivered_keys': [multi['keys'][i].tolist() for i in delivered],
                   'delivered_query_tags': [int(multi['best_query_tag'][i]) for i in delivered],
                   'delivered_graph_tags': [
                       prepared.graph_tags[prepared.edge_tag[best_edge[i]]]
                       if best_edge[i] >= 0 else None for i in delivered],
                   'query_facet_orders': [
                       {'side': side, 'tag': name,
                        'readings': dict(zip(R4.ADJUST_FACETS,
                                             (float(readings[j]) for j in facet_columns))),
                        'order': list(slot_facets)}
                       for side, name, (_, readings), slot_facets
                       in zip(sides, names, query_tags, multi['facet_orders'])]}
        picked = None
    elif flags['sort'] == 'adjust_lower':
        diagnostics.update(adjust_lower_meta(lower, tag_score, reached, text_cosines, rank,
                                             delivered, flags['descjoin']))
        diagnostics.update(score_stats)
        diagnostics['product_named_tags_excluded_casefold'] = int((~eligible).sum())
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_scores': [float(lower['score'][i]) for i in delivered],
                   'delivered_reached': [bool(reached[i]) for i in delivered]}
        picked = None
    elif flags['sort'] == 'multirank':
        diagnostics.update(multirank_meta(multi, text_cosines, rank, delivered))
        diagnostics['product_named_tags_excluded_casefold'] = int((~eligible).sum())
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_strength_levels': [int(multi['fit_level'][i]) for i in delivered],
                   'delivered_column_orders': [
                       [R4.ALL_FACETS[j] for j in multi['columns'][i]] if i in multi['columns']
                       else None for i in delivered],
                   'delivered_edge_levels': [multi['edge_levels'][i].tolist() for i in delivered]}
        picked = None
    elif flags['sort'] == 'concept':
        diagnostics.update(concept_meta(prepared, concept, delivered))
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_scores': [float(concept['score'][i]) for i in delivered]}
        area_meta = {'mode': 'not read by the concept sort'}
        picked = None
    elif flags['sort'] == 'chain':
        diagnostics.update(chain_meta(prepared, chain, delivered))
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_fit_levels': [int(chain['best_fit_level'][i]) for i in delivered],
                   'delivered_rel_levels': [int(chain['best_rel_level'][i]) for i in delivered],
                   'delivered_description_cosines':
                       [float(text_cosines['description'][i]) for i in delivered]}
        area_meta = {'mode': 'not read by the chain sort'}
        picked = None
    else:
        tag_component = parts['tag_part'] if facets_on else parts['tag_part_plain']
        use_tags = flags['probes'] in ('all', 'tags')
        use_text = flags['probes'] in ('all', 'text')
        tag_values, text_values, shares = [], [], []
        for i in delivered:
            t = float(tag_component[i]) if use_tags else 0.
            x = float(parts['text_part'][i]) if use_text else 0.
            tag_values.append(t)
            text_values.append(x)
            scale = abs(t) + abs(x)
            shares.append(None if scale == 0. else abs(x) / scale)
        known = [v for v in shares if v is not None]
        no_adjust = combine_parts({**parts, 'tag_part': parts['tag_part_plain']},
                                  probes=flags['probes'], facets_on=False)
        diagnostics.update({
            'tag_part_of_delivered_score': tag_values,
            'text_part_of_delivered_score': text_values,
            'text_share_of_delivered_score': shares,
            'mean_text_share': (sum(known) / len(known)) if known else None,
            'undefined_shares': len(shares) - len(known),
            'flip_fraction_facets_off': (_flip_fraction(delivered, no_adjust, rank)
                                         if facets_on and use_tags else None),
            'flip_fraction_text_probes_off': (_flip_fraction(delivered, tag_component, rank)
                                              if use_text and use_tags else None),
            'adjust_eta2_by_record_kind_over_reached_probe_edge_pairs':
                _eta_squared(parts['adjust'], parts['adjust_kind']),
            'reached_probe_edge_pairs': int(parts['adjust'].size),
        })
        ranking = {'ordered_chunk_ids': [prepared.chunk_ids[i] for i in order],
                   'delivered_chunk_ids': [prepared.chunk_ids[i] for i in delivered],
                   'delivered_scores': [float(total[i]) for i in delivered]}
        picked = parts['picked_counts']
    retrieval = ModelUsage(**{name: getattr(interp_usage, name) + getattr(embed_usage, name)
                              for name in ModelUsage.__dataclass_fields__})
    for name, value in chat.take_timing().items():
        setattr(retrieval, name, value)
    if flags['sort'] in ('strength', 'multikey', 'adjust_lower', 'multirank', 'walk'):
        excluded = int((~np.asarray(eligible, dtype=bool)).sum())
    elif flags['sort'] == 'concept' or flags['tagside'] == 'nonscope':
        excluded = int((~np.asarray(prepared.nonscope_eligible, dtype=bool)).sum())
    else:
        excluded = 0
    meta = {'policy': {**RETRIEVAL_FLAGS, 'resolved': flags, 'knobs_recorded': knob_record(flags),
                       'band_value': band if flags['sort'] == 'sum' else None,
                       'fit_equal_width': (BANDS[flags['fiteq']] if flags['sort'] == 'multikey'
                                           else None),
                       'struct_at': flags['structat'] if flags['sort'] == 'multikey' else None,
                       'facet_gaps': (dict(zip(R4.ADJUST_FACETS,
                                               prepared.multikey_layer.gaps.tolist()))
                                      if flags['sort'] == 'multikey' else None),
                       'facet_gap_source': (prepared.multikey_layer.gap_source
                                            if flags['sort'] == 'multikey' else None),
                       'facet_value_source': (prepared.multikey_layer.value_source
                                              if flags['sort'] == 'multikey' else None),
                       'product_named_tags_excluded': excluded,
                       'flip_gap': (prepared.rank_layer.gap
                                    if flags['sort'] == 'multirank'
                                    and prepared.rank_layer is not None else None)},
            'provenance': prepared.provenance,
            'interpreter': {'model': INTERPRET_MODEL, 'stages': stages, 'texts': branch_meta,
                            'query_tags': len(query_tags),
                            'description_side_tags': len(tags),
                            'question_side_tags_in_answer': len(query.query_tags),
                            'question_side_tags_read': len(question_side),
                            'text_probes': (
                                len(text_cosines) if flags['sort'] == 'sum'
                                and flags['probes'] in ('all', 'text')
                                else len(diagnostics['texts_in_the_strength']) if by_walk
                                else 0),
                            'picked_graph_tags_per_probe': (picked if flags['probes']
                                                            in ('all', 'tags') else None)},
            'area': area_meta, 'ranking': ranking,
            'diagnostics': diagnostics, 'chunk_ids': id_lists,
            'returned': len(contexts), 'char_budget': budget}
    search_time = max(0., time.perf_counter() - started - interp_usage.time_s)
    if generate is None:
        answer, gen_usage = '', ModelUsage()
    else:
        gen_started = time.perf_counter()
        answer, gen_usage = unpack_generation(generate(text, contexts),
                                              time.perf_counter() - gen_started)
    return ArmOutput(answer=answer, contexts=contexts, context_ids=context_ids,
                     search_time_s=search_time, generator=gen_usage, retrieval=retrieval,
                     meta=meta)
