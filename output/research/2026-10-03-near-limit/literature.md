# Which graph tags count as near a query tag — what the research has, 2026-10-03

His question (2026-10-03): *"the fucking point of using the embeddings is to find the nearness of
them.."* · *"so, how DO we limit that? what does the research say?"*

His rules this review is held to: *"i do NOT like arbitrary choices for k or any number or value,
fucking BASE it on something"* (2026-07-15); *"let clustering hand me the k, those fixed numbers
are enraging me"* (2026-09-07); *"perhaps we should have the order slightly fuzzy, meaning … things
can be called "equal" if within a certain range of eachother"* (2026-09-06); no design chosen on
the gold; and his two steps (2026-10-03): step 1 hit all the correct chunks, step 2 float the
correct ones — so the limit is judged on coverage, a pool much smaller than the corpus that still
holds the right chunks.

## 0. Where every fact in this file comes from

- **Literature.** Each source carries a mark for how it was read this session:
  **[FT]** full text fetched (HTML / ar5iv / PMC) and queried through the fetch tool's extraction —
  not read page by page by me; numbers are as the extraction returned them.
  **[AB]** abstract or publisher / anthology page only.
  **[SEC]** known through another paper's, a survey's or a library's description.
  **[MEM]** cited from memory, not re-checked this session.
- **The instrument.** Every number about the fit lists is from
  `output/research/2026-10-03-evidence-design/instrument.md`, a report on disk read in full this
  session. I did not re-run it. No graph query was run this session.
- **Code read this session.** The embedder is `nvidia/llama-nemotron-embed-1b-v2`, prefixes
  `query: ` / `passage: ` (`prod/harness/embed.py` line 11; `test/arms/artefact_facet_joint.py`
  lines 298–301).
- **Not opened.** No question text, no gold, no `arm_outputs.jsonl`.
- Paragraphs headed **Literature** say what the papers say. Paragraphs headed **Mine** are my
  reasoning and are nobody's result.

The instrument in one paragraph (instrument.md, sections A, B, D, H): one query tag against
16,609 graph tags; bulk 0.108, spread s 0.029; upper tail exponential-like (top-100 mean excess
1.06 s; a normal list of that size 0.32 s); top-1 / top-10 / top-100 at 8.58 / 6.37 / 3.97 s; a
break in the top 100 on 8 of 100 lists (12 by the second detector), never after ranks 1–5; top-1
minus top-2 0.34 s; a graph tag's own name in the query role reaches its stored vector at cosine
0.474 (0.274–0.717), rank 1 on 85.7%, worst rank 18; in the passage role 0.991 (0.975–0.995),
rank 1 on 100%; 63% of tags sit on one chunk; above the universal threshold 67 tags (3–383)
reaching 240 chunks (5–1,003) per query tag; "realness" above 0.5 on 834 tags (37–2,220).

## 1. Ranked-list truncation in IR

**Literature.**

- Arampatzis, Kamps & Robertson 2009 (SIGIR) [AB; the TREC-2008 notebook version's contents and
  conclusions page FT]. Fit a normal (relevant) + exponential (non-relevant) mixture to one query's
  scores by EM, no labels, then pick the rank that optimises F1 from the estimated counts. They
  name two theoretical faults of the mixture — support incompatibility and recall-fallout
  non-convexity — and add truncated variants. Their own conclusion: "the effectiveness varies
  considerably per topic, with an average performance of 75-80% of F1@R".
- Lien, Cohen & Croft 2019 (ICTIR), BiCut [AB]: a Bi-LSTM over the score sequence, trained on
  relevance labels.
- Bahri, Tay, Zheng, Metzler & Tomkins 2020 (SIGIR), Choppy [FT]: a Transformer over the scores
  alone, trained on relevance labels to optimise a chosen metric. Robust04, BM25, F1: Oracle 0.367,
  Fixed-k(50) 0.239, Greedy-k 0.248, BiCut 0.244, Choppy 0.272.
- Wu, Zhang, Guo, Fan, Lan & Cheng 2021 (AAAI), AttnCut [FT]: Transformer + reward-augmented
  likelihood, trained on labels; also the objective "best F1 under a minimal recall constraint".
  Robust04 BM25 F1: Oracle 0.3591, Greedy-k 0.2538, BiCut 0.2513, Choppy 0.2738, AttnCut 0.2821.
- Bahri, Zheng, Tay, Metzler & Tomkins 2023 (SIGIR; arXiv 2010.09797), Surprise [FT]: fit a
  Generalized Pareto distribution to the non-relevant scores' excesses (threshold found by a greedy
  Cramér–von-Mises search, no fixed tail size), rescore each result as −log of its tail
  probability. The rescoring uses no labels; the cut is a threshold on that score "that optimizes
  the target metric", tuned on labelled training data (grid over [0, 8]). Premise stated by the
  authors: the system ranks relevant above non-relevant with high probability. Robust04 DRMM F1:
  Surprise 0.268, Global-k 0.263, BiCut 0.262.
- Meng, Arabzadeh, Askari, Aliannejadi & de Rijke 2024 (arXiv 2404.18185; venue SIGIR 2024 from
  memory) [FT]: eight truncation methods reproduced before LLM re-ranking, TREC-DL 19/20, three
  retrievers, two re-rankers. "Supervised RLT methods do not demonstrate a clear advantage over
  their unsupervised counterparts; potential fixed re-ranking depths can closely approximate the
  effectiveness/efficiency trade-off achieved by supervised methods." With SPLADE++ or RepLLaMA a
  fixed depth of 20 gave the best trade-off in every scenario.
- Taguchi, Maekawa & Bhutani 2025 (EMNLP; arXiv 2506.08479), Adaptive-k [FT]: sort the cosines,
  cut at the largest drop between consecutive items. Two constants ride along: a buffer of B = 5
  further items and a restriction of the search to the top 90% of the list. About 70% context
  recall on HoloBench at 2–10× fewer tokens. The paper does not treat a list with no clear drop.
- Song, Fang, Li, Xia & Wang 2026 (arXiv 2606.11907), TAA-k [AB]: knee detection to find a
  candidate window, then an extreme-value goodness-of-fit test inside it; the abstract rests it on
  a "steep–flat–steep" shape of the similarity curve.

What the family needs: either relevance labels to train on (BiCut, Choppy, AttnCut and the later
MtCut, LeCut named in Meng et al.), or a distribution assumption plus an optimisation target
(Arampatzis; Surprise's threshold), or a visible drop (Adaptive-k, TAA-k). What it is judged by:
F1 and a penalised DCG — a balance of precision and recall of the final list, not coverage.
Evidence: the learned truncators recover roughly a fifth to a quarter of the distance from
Greedy-k to the oracle on Robust04; in re-ranking pipelines a fixed depth is not beaten.

**Mine.** The labels these methods train on are the gold; that route is closed by his rule. The
unsupervised ones need the shape the instrument does not have. Under an exponential tail Surprise's
score for the item at rank i of a tail of n is about ln(n/i) — the prototype's own S_tag =
ln(N/rank) — so on these lists Surprise restates the rank and its threshold is a rank fraction: the
number comes back in. The largest-drop rule on these lists would cut where the largest spacing
happens to fall (instrument: after rank 2 at the median, 1–41), which the instrument shows is the
tail's own spacing (largest normalised spacing 5.00 against 4.32 for an exponential tail).

## 2. Score-distribution models, extreme values, meta-recognition

**Literature.**

- Manmatha, Rath & Feng 2001 (SIGIR) [AB]: per query, non-relevant scores fit an exponential and
  relevant scores a normal; shown on TREC-3/4 for several engines; used to turn scores into
  probabilities for fusion.
- Arampatzis & Robertson 2011 (Information Retrieval 14(1)) [AB]: reviews the mixtures, states the
  conditions a valid one must meet (the recall-fallout convexity hypothesis), argues two gammas are
  the likely universal model and normal–exponential a usable approximation.
- Kanoulas, Dai, Pavlu & Aslam 2010 (SIGIR) [SEC]: a mixture of Gaussians for relevant, a gamma for
  non-relevant.
- Scheirer, Rocha, Micheals & Boult 2011 (TPAMI 33(8)) [AB]: meta-recognition — by extreme value
  theory the tail of the non-match scores of one recognition instance follows an extreme-value
  (Weibull) law; fit it, and ask whether the top score is an outlier of that tail; a per-instance
  prediction that recognition succeeded.

What the family needs: no labels; a model of the non-match scores (the bulk, or the tail); a tail
size to fit on; and a level at which "outlier" is declared (a significance level — a stated risk,
by convention). It is built to find a top that stands apart from the tail.

**Mine.** The instrument already ran this family: spacings against an exponential tail (Rényi,
Fisher), the universal threshold, the empirical null. The outcome is the family's answer for this
instrument. Read against the tail, nothing stands apart: a break on 8–12 of 100 lists, the rank-1
test passed by 0 of 100 query tags, and by only 69 of 300 lists that hold a certain match (a tag's
own name). Read against the bulk, hundreds stand apart (834 at realness 0.5, 258 at 0.9) and the
count ranges over two orders of magnitude. The literature's own model says why: the non-relevant
scores at the top of a list ARE an exponential tail (Manmatha; Arampatzis), which is the measured
shape, so the top of these lists is what the model calls background. A rule of this family returns
either zero or hundreds here, depending on which null it takes.

## 3. Hubness and local scaling

**Literature.**

- Radovanović, Nanopoulos & Ivanović 2010 (JMLR 11) [AB]: in high dimension the number of times a
  point appears among others' k nearest neighbours becomes strongly skewed; a few hubs are near
  everything, antihubs near nothing; a property of the space, not of one data set.
- Zelnik-Manor & Perona 2004 (NIPS) [SEC]: local scaling — divide the squared distance by the
  product of the two points' own scales, σ_i = distance to the K-th neighbour; they used K = 7.
- Schnitzer, Flexer, Schedl & Widmer 2012 (JMLR 13) [AB; the formula SEC through Feldbauer &
  Flexer]: mutual proximity. Empirical form, no parameter:
  MP(x, y) = |{j : d(x,j) > d(x,y)} ∩ {j : d(y,j) > d(y,x)}| / (n − 2) — the share of the
  collection that is farther from x than y is and farther from y than x is.
- Conneau, Lample, Ranzato, Denoyer & Jégou 2018 (ICLR) [SEC]: CSLS(x, y) = 2·cos(x, y) − r(x) −
  r(y), r being the mean cosine to the K nearest neighbours on the other side; K = 10.
- Feldbauer & Flexer 2019 (Knowledge and Information Systems; PMC7327987) [FT]: twelve reduction
  methods on 50 data sets; local scaling, NICDM, mutual proximity and DisSimLocal are the state of
  the art; the scaling methods "yield significantly better results" than the baseline in nearest-
  neighbour classification; little change on low-hubness data. Empirical mutual proximity has no
  parameter; local scaling and NICDM need k.
- Bogolin, Croitoru, Jin, Liu & Albanie 2022 (CVPR) [AB]: querybank normalisation — in a
  query-versus-gallery setting, normalise each gallery item's similarities against a bank of
  queries; works without the test queries.

What the family gives: a corrected nearness in which each side is read against its own
neighbourhood — a better order and a comparable scale. It does not cut. Made-up numbers: K in
local scaling and CSLS; none in empirical mutual proximity. A gap is not needed.

**Mine.** The instrument measured one half of this already: a query tag's raw top-1 cosine follows
its own background (Spearman 0.58) and its standardised top-1 does not (0.05) — nearness has to be
read in the query tag's own scale. The other half, the graph tag's own scale (is this graph tag
near everything?), is not measured anywhere I read: no k-occurrence skew, no hub count.

## 4. Mutual / reciprocal neighbours

**Literature.**

- Jégou, Schmid, Harzallah & Verbeek 2010 (TPAMI 32(1)) [AB]: nearest-neighbour relations are not
  symmetric; the contextual dissimilarity measure corrects distances iteratively from each
  vector's local neighbourhood.
- Qin, Gammeter, Bossard, Quack & Van Gool 2011 (CVPR) [AB]: the k-reciprocal neighbour structure
  marks the part of a ranked list that is reliably related; different parts of the list are then
  treated with different measures.
- Zhong, Zheng, Cao & Li 2017 (CVPR; arXiv 1701.08398) [FT]: R(p, k) = {g : g ∈ N(p, k) and
  p ∈ N(g, k)}. Constants: k1 = 20, k2 = 6, λ = 0.3 (7, 3, 0.85 on another set), an expansion with
  ½k and a ⅔ overlap, tuned on a labelled validation split. Market-1501 mAP 49.05 → 63.63.
- Ozaki, Shimbo, Komachi & Matsumoto 2011 (CoNLL) [AB]: mutual k-NN graphs beat k-NN graphs on
  language data and resist hub vertices.
- Korn & Muthukrishnan 2000 (SIGMOD) [AB]: the reverse nearest neighbours of q are the points that
  have q as THEIR nearest neighbour — the "influence set"; no k, a set whose size the data gives.
- Papadakis, Koutrika, Palpanas & Nejdl 2014 (TKDE) and Papadakis, Papastefanatos, Palpanas &
  Koubarakis 2016 (EDBT) [both SEC through the 2020 survey, FT]: in candidate pruning for entity
  resolution, "reciprocal" pruning keeps a pair only if it passes in BOTH nodes' neighbourhoods;
  it raises precision over the one-sided form.

What the family needs: no labels; the second direction — the graph tag's own neighbours — and both
directions on scales that can be compared. A number: k, in every published k-reciprocal form; none
when k = 1 (reverse nearest neighbour). A gap is not needed; it reads ranks. Evidence: consistent
gains as a re-ranking and pruning device, measured on precision-type metrics; the entity-resolution
survey states that reciprocity is the aggressive form — precision up, recall down.

**Mine.** This is the nearest translation in the literature of a nearness the data limits by
itself: a graph tag is near the query tag when the query tag also stands inside the graph tag's
own neighbourhood. Two facts of the instrument bound it. The two directions are not on one scale
in the arm as it runs (query role against passage role: bulk 0.108; passage against passage: bulk
0.735), so the relation must be read by rank on each side, or with the query tag in the passage
role (H: identity 0.975–0.995 there). And reciprocity is a precision device, while his limit serves
coverage; whether it keeps the right chunks is not known.

## 5. Data-adaptive neighbourhoods; knee and gap rules

**Literature.**

- Shekkizhar & Ortega 2020 (ICASSP; long version arXiv 1910.09383) [FT], NNK: among an initial
  k-NN set, solve a non-negative kernel regression of the query on its neighbours; a neighbour gets
  weight zero when a closer neighbour lies in the same direction (the kernel-ratio-interval
  condition; geometrically each kept neighbour's hyperplane cuts away what lies behind it). The
  number kept "saturates for increasing k" and reflects local geometry. Inputs: the initial k and a
  kernel (their Gaussian bandwidth is tied to the k-th neighbour distance through a factor 3).
  70 OpenML sets: 16.26% error against 18.06% for k-NN.
- Zhu, Feng & Huang 2016 (Pattern Recognition Letters), natural neighbours [SEC]: grow r = 1, 2, …;
  two points are natural neighbours when each is among the other's r nearest; stop when the number
  of points nobody names stops changing; that r is the data set's own k.
- Satopää, Albrecht, Irwin & Raghavan 2011 (ICDCS Workshops), Kneedle [SEC, library docs]: smooth
  the curve, normalise both axes to the unit square, take the point of largest departure from the
  diagonal; a sensitivity parameter S.
- Schubert 2023 (SIGKDD Explorations 25(1)) [AB]: the elbow criterion "severely lacks theoretic
  support"; its reading depends on how the axes are drawn.

**Mine.** NNK needs no gap and its initial k can be taken large, so it comes close to number-free;
but what it removes is the near tag that sits behind a nearer one — a near-duplicate. With 63% of
tags on a single chunk, two near-duplicate graph tags lead to different chunks, so the removal
works against coverage. Natural neighbours hand over one k for the whole tag set, not per query
tag, and antihubs (Radovanović) keep the stopping rule waiting; I could not read the original.
The knee on a gapless exponential tail is set by the window, not by the list: if the score at rank
i is c − s·ln i over a window of W ranks, the unit-square knee falls at i* = W / ln W — rank 22
for W = 100, 145 for W = 1,000, 1,709 for W = 16,609. The window is the made-up number.

## 6. Density and fuzzy clustering

**Literature.**

- Campello, Moulavi & Sander 2013 (PAKDD), HDBSCAN [AB; the library's parameter page FT]: clusters
  are the stable branches of the density hierarchy; parameters `min_cluster_size` and
  `min_samples`; points in thin regions are labelled noise; by default it "does not allow a single
  cluster to be returned".
- Ankerst, Breunig, Kriegel & Sander 1999 (SIGMOD), OPTICS [MEM]: a reachability ordering whose
  valleys are the clusters; parameter MinPts.
- Bezdek 1981, fuzzy c-means [MEM]: needs the number of clusters c and a fuzzifier m; a point's
  memberships sum to one. Krishnapuram & Keller 1993 (IEEE TFS), possibilistic c-means [SEC]:
  drops the sum-to-one constraint so membership is absolute typicality; needs a scale per cluster;
  Barni, Cappellini & Mecocci 1996 [SEC]: it tends to produce coincident clusters.
- Tibshirani, Walther & Hastie 2001 (JRSS B 63) [SEC]: the gap statistic compares within-cluster
  dispersion with that of a structureless reference and can return one cluster.

**Mine.** On a list with one mode and a smooth tail a density method has one branch: it returns a
single cluster or noise, so it hands over no k. A partitioning method told to make two groups
always makes two, split where the masses balance — a cut the list does not contain. The gap
statistic is the honest member: its answer on such a list is "one". This is the fit LIST. Whether
the 16,609 graph tags themselves form groups in the embedding space — areas a query tag could land
in — is a different object and is not in the instrument.

## 7. Not cutting: graded nearness

**Literature.**

- Query expansion with embedding neighbours. Kuzi, Shtok & Kurland 2016 (CIKM) [AB]; Roy, Paul,
  Mitra & Garain 2016 (Neu-IR workshop; arXiv 1606.07608) [AB]: the k nearest terms as expansion —
  better than no expansion, "significantly inferior to RM3". Zamani & Croft 2016 (ICTIR) [SEC]:
  pass the cosines through a sigmoid "to have more discriminative semantic similarity values"
  before using them as weights. In this line the number of expansion terms and the weighting are
  free parameters set on labelled collections [MEM for the specifics].
- Rekabsaz, Lupu, Hanbury & Zuccon 2017 (ECIR; arXiv 1606.06086) [FT]: the one paper found that
  DERIVES the similarity threshold. Train the same embedding several times from different seeds;
  the spread of a pair's similarity across trainings is the instrument's uncertainty; from it, the
  expected number of neighbours at each similarity level; the threshold is where that expectation
  equals the average number of synonyms of a word in WordNet, 1.6. Thresholds 0.818 / 0.756 /
  0.708 / 0.675 at 100 / 200 / 300 / 400 dimensions; retrieval "equal to or statistically
  indistinguishable from the optimal" threshold. One imported constant: the 1.6.
- Khattab & Zaharia 2020 (SIGIR), ColBERT [FT]: score = Σ over query vectors of the maximum cosine
  over the document's vectors; no threshold in the score. The candidate set for that score is the
  union of the top-k′ per query vector, "e.g., k′ = k/2" — a constant.
- Entity linking. Wu, Petroni, Josifoski, Riedel & Zettlemoyer 2020 (EMNLP), BLINK [FT]: candidates
  are the top 64 / top 100 / top 10 of a bi-encoder, judged by recall@k (82.06% against BM25's
  69.13% at 64; 98.3% against 68.9% at 100), k taken from the accuracy trade-off on labelled data;
  "prior work often used a fixed number of k candidates where k ranges from 5 to 100". Hachey,
  Radford, Nothman, Honnibal & Curran 2013 (Artificial Intelligence 194) [AB]: the search step
  accounts for much of the variation between linking systems.

What the family needs: nothing at the tag list — every neighbour counts in proportion to its
nearness. The limit moves to the candidate pool, and there the literature uses a fixed size read
off a labelled recall curve or a compute budget. No number-free pool size was found.

**Mine.** The instrument shows what "no cut" does here: three or more query tags give nonzero
evidence to 4,659–4,803 of the 4,808 chunks, so grading alone makes no pool. It also shows the
grading can be made fair to chunks with many tags (exact chance correction: Spearman with the tag
count 0.04). Rekabsaz's first half transfers without its constant: the instrument's uncertainty —
how far the same thing lands from itself — is a measured width inside which two nearnesses are the
same, his "equal within a range". The instrument has two such widths: the passage-role
reproduction of a stored tag vector (0.991, 0.975–0.995) and the query-role distance of a name
from its own vector (0.474, 0.274–0.717).

## 8. Calibration on labels

**Literature.**

- Angelopoulos, Bates, Fisch, Lei & Schuster 2024 (ICLR), conformal risk control [AB]: choose the
  threshold so that the expected value of a monotone loss — their worked example includes the
  false-negative rate — stays below a level α, with a guarantee tight to O(1/n). Li, Park, Lee &
  Bastani 2024 (NAACL), TRAQ [AB]: the same idea for the retrieval set in retrieval-augmented
  answering.
- Cormack & Grossman 2016 (SIGIR) [AB; the constants SEC through later stopping-rule papers]:
  stopping rules for total-recall review; the "target" rule samples until 10 relevant documents are
  found and guarantees 70% recall; the "knee" rule stops at a slope ratio of 6. Both use relevance
  judgements made during the review.
- Azzopardi, de Rijke & Balog 2007 (SIGIR) [AB]: known-item queries can be simulated from the
  documents themselves and used for evaluation.

Stated plainly: this family needs labels — pairs of (query, the items that are truly right for
it), drawn like the queries it will be used on — and one chosen level α, the miss rate accepted.
It needs no gap and no distribution. It is the only family with a guarantee on coverage.

**Mine.** The benchmark's gold is the only such label set in the repo, and calibrating on it is
choosing on the gold. A label set that is not the gold exists inside the graph: a tag's own name
as the query and the tag as the right answer (the instrument's identity probes; Azzopardi's
known-item simulation). The guarantee does not carry over, because the names are not drawn like
real query tags (identity lists: own tag 11.6 s above the bulk; query tags' best 8.58 s). And α
remains a number someone states.

## 9. What a limit is judged by when its purpose is coverage

**Literature.**

- Candidate pruning in entity resolution, Papadakis, Skoutas, Thanos & Palpanas 2020 (ACM Computing
  Surveys; arXiv 1905.06167) [FT] and Christen 2012 (TKDE 24(9)) [AB]: three measures, always
  reported together. Pair completeness = the share of the true matches that survive in the pool
  (recall). Reduction ratio = 1 − pool size / all pairs. Pairs quality = the share of the pool that
  is a true match (precision). "Blocking trades slightly lower effectiveness for significantly
  higher efficiency." The same survey lists pruning thresholds read from the data instead of set:
  drop every pair below the AVERAGE weight (weighted edge pruning); per node, drop what is below
  the average of that node's own neighbourhood (weighted node pruning); a global size of half the
  sum of the block sizes (cardinality edge pruning) [the last SEC]; and the reciprocal forms.
- Entity linking: recall@k of the candidate set, with k (BLINK, above).
- Truncation: Fixed-k and Greedy-k of the same length are the controls, the oracle cut the ceiling
  (Choppy, AttnCut, Meng et al., above). AttnCut's "best F1 under a minimal recall constraint" is
  the truncation literature's nearest objective to coverage.
- Total-recall review: the share of all relevant items reached, with the effort spent (Cormack &
  Grossman).

So the literature's answer: coverage of the right items in the pool, stated together with the
pool's size (as a share of everything), per query and on average; against a pool of the same mean
size made by plain rank; with the best order of that pool as the ceiling for step 2. Not F1, not
the final order.

**Mine.** A coverage measure that touches no gold is available for any limit rule: a tag's own
name as the query tag — does the rule's near set contain the tag (instrument: rank 1 on 85.7%,
within 10 on 99.3%, worst 18).

## 10. The families side by side

| family | needs | a made-up number? | works with no gap? | evidence |
|---|---|---|---|---|
| 1 learned truncation (BiCut, Choppy, AttnCut) | relevance labels to train | none in the rule; the labels are the gold | yes | 0.25 → 0.27–0.28 F1 against an oracle 0.36; fixed depth not beaten before re-ranking (Meng 2024) |
| 1 largest drop / knee (Adaptive-k, TAA-k) | a visible drop | B = 5, top 90%; window | no | ~70% context recall on its own benchmarks; gapless case not treated |
| 2 score mixtures, extreme values, meta-recognition | a model of the non-match scores; a level | tail size, significance level | returns zero (tail null) or hundreds (bulk null) | 75–80% of F1@R, varying by topic (Arampatzis); on this instrument: 0 of 100 and 834 |
| 3 hubness scaling (local scaling, CSLS, mutual proximity) | each side's own neighbourhood | K = 7, K = 10; none in empirical mutual proximity | yes | best-in-class over 50 data sets (Feldbauer & Flexer); gives order and scale, no cut |
| 4 mutual / reciprocal / reverse neighbours | the second direction, comparable | k in published forms; none at k = 1 | yes | precision gains in re-ranking and pruning; recall falls |
| 5 NNK, natural neighbours | initial set, kernel | nearly none (NNK); none (natural) | yes | 16.3% vs 18.1% error (NNK); drops near-duplicates |
| 5 Kneedle | a curve and a window | S, the window | returns W / ln W | "lacks theoretic support" (Schubert) |
| 6 density and fuzzy clustering | a density with more than one mode | min_cluster_size; c, m | one cluster, noise, or an artefact split | — |
| 7 no cut, graded nearness; candidate pools | nothing at the tag; a pool size | the pool size (k′ = k/2; 64; 100) | yes | standard practice; pool size from labelled recall@k |
| 7 threshold from the instrument's own uncertainty (Rekabsaz) | repeated measurements of the same pair | the imported 1.6 | yes | indistinguishable from the tuned optimum |
| 8 conformal risk control | labelled pairs like the real queries | α, the stated miss rate | yes | a proven bound on the miss rate |

## 11. Which fit his rules and this instrument, and which do not (mine)

**Fit best.**

1. *A two-sided nearness, each side read in its own scale* (families 3 and 4; in his words, an
   area around the query tag whose size the tags hand over). Empirical mutual proximity and the
   reverse-nearest-neighbour relation carry no number, need no gap, and read ranks, which is what
   the role asymmetry and the 0.58 background dependence require. Missing: the graph tags' own
   neighbourhoods have not been measured; reciprocity favours precision.
2. *A width read off the instrument's own repeat of a known match* (Rekabsaz's method without its
   constant; the identity probes). It is the literature's one derived threshold, it is his "equal
   within a range", and its inputs are already measured (0.991 / 0.975 in the passage role; 0.474
   / 0.274 in the query role). It marks "the same tag", one or two graph tags for 30 of 100 query
   tags in the passage role; it does not by itself say how far "related" reaches.
3. *No cut at the tag; graded nearness in the list's own units; the limit on the pool, reported as
   coverage against pool size* (family 7 and section 9). This is what the literature does where
   the purpose is coverage. The pool size is not derived anywhere in the literature; the data-read
   thresholds of the pruning literature (the average weight, the node's own average) are the
   nearest thing to a size that is not chosen.

**Plainly do not fit.**

- The largest-drop and knee rules: there is no drop; the knee is the window.
- Score mixtures, extreme-value outlier tests, meta-recognition: zero or hundreds on these lists.
- The trained truncators and conformal calibration on the benchmark: both are the gold.
- HDBSCAN, OPTICS, fuzzy and possibilistic c-means on the fit list: one mode.
- Published k-reciprocal encoding, local scaling with K = 7, CSLS with K = 10: constants tuned on
  labels or by habit.
- NNK: within the rules, against the purpose (removes near-duplicates that hold other chunks).

**If one of the three is measured — stated before anything runs.**

| | hypothesis | control | decision rule |
|---|---|---|---|
| 1 | the two-sided near set holds the right chunks in a pool smaller than a one-sided set of the same size | the nearest graph tags by plain rank, the same number per query tag | pair completeness at equal pool size, paired per question, gold by id only through the harness; the rule adds something only if the paired difference is separated (paired bootstrap over questions); gold-free first: own-name coverage and the pool-size distribution |
| 2 | graph tags within the measured repeat width of the best one are one level | the same walk with the 0.002 step instrument.md reports as the arm's first key (not read in the arm's code by me) | number and size of levels, gold-free; then coverage per level opened |
| 3 | grading with the chance correction and no tag cut, pool cut by a data-read threshold, covers more at a given pool size than a tag cut | a fixed-size pool of the same mean size | pair completeness against reduction ratio, the whole curve reported, per route and for the union |

## 12. Not verified

- Scheirer et al. 2011: abstract only; the tail size and the outlier level they use were not read.
- Arampatzis, Kamps & Robertson 2009: the SIGIR paper itself was not read; the section titles and
  the conclusion are from the TREC-2008 notebook version. An earlier extraction of the PDF gave a
  description of the theoretical problems that I do not trust and did not use.
- Zhu, Feng & Huang 2016 (natural neighbours): the original could not be fetched; the algorithm
  and stopping rule are from secondary descriptions; volume and pages not checked.
- Zamani & Croft 2016: only the sentence on the sigmoid transform was confirmed; the paper's
  remark that the 1,000th nearest term is nearly as similar as the first is from memory.
- Zelnik-Manor & Perona's K = 7 and Conneau et al.'s K = 10: from secondary descriptions; that
  CSLS is stable for other K is from memory.
- Kneedle: from the `kneed` library's description, not the paper.
- OPTICS, fuzzy c-means, the per-cluster scale in possibilistic c-means, Hartigan's dip test,
  reciprocal best hits in genomics, MS MARCO's recall@1000 convention: from memory, not cited as
  evidence above.
- Cormack & Grossman's constants (10 relevant; slope ratio 6; 70% recall): through a search
  summary of later papers.
- The pruning literature's cardinality formulas: through a search summary; only the "average
  weight" thresholds were read in the survey text.
- Meng et al. 2024: the venue (SIGIR 2024) is from memory; the content is from arXiv v1.
- Song et al. 2026 (TAA-k): abstract only.
- Every [FT] number came through the fetch tool's extraction of the page, not from my reading of
  the PDF; the three PDFs I tried to open directly could not be rendered on this machine.
- Hubness of the graph tags (k-occurrence skew), whether the graph tags cluster in the embedding
  space, and the union over a question's 7–13 query tags of the chunks above the universal
  threshold: not in the instrument, not measured by me.
- The embedder's model card says nothing on using either prefix for phrase-to-phrase similarity;
  whether its cosines are meant to be compared across queries is not stated there.
- The W / ln W knee is my derivation for a list whose score falls as the log of the rank; not
  checked on the real arrays.

## References

Angelopoulos, A. N., Bates, S., Fisch, A., Lei, L. & Schuster, T. (2024). Conformal risk control. ICLR. [AB]
Ankerst, M., Breunig, M., Kriegel, H.-P. & Sander, J. (1999). OPTICS: ordering points to identify the clustering structure. SIGMOD. [MEM]
Arampatzis, A., Kamps, J. & Robertson, S. (2009). Where to stop reading a ranked list? Threshold optimization using truncated score distributions. SIGIR. [AB; TREC-2008 version partly FT]
Arampatzis, A. & Robertson, S. (2011). Modeling score distributions in information retrieval. Information Retrieval 14(1). [AB]
Azzopardi, L., de Rijke, M. & Balog, K. (2007). Building simulated queries for known-item topics: an analysis using six European languages. SIGIR. [AB]
Bahri, D., Tay, Y., Zheng, C., Metzler, D. & Tomkins, A. (2020). Choppy: cut transformer for ranked list truncation. SIGIR. arXiv 2004.13012. [FT]
Bahri, D., Zheng, C., Tay, Y., Metzler, D. & Tomkins, A. (2023). Surprise: result list truncation via extreme value theory. SIGIR. arXiv 2010.09797. [FT]
Barni, M., Cappellini, V. & Mecocci, A. (1996). Comments on "A possibilistic approach to clustering". IEEE Trans. Fuzzy Systems 4(3). [SEC]
Bezdek, J. C. (1981). Pattern Recognition with Fuzzy Objective Function Algorithms. Plenum. [MEM]
Bogolin, S.-V., Croitoru, I., Jin, H., Liu, Y. & Albanie, S. (2022). Cross modal retrieval with querybank normalisation. CVPR. [AB]
Campello, R., Moulavi, D. & Sander, J. (2013). Density-based clustering based on hierarchical density estimates. PAKDD. [AB]
Christen, P. (2012). A survey of indexing techniques for scalable record linkage and deduplication. IEEE TKDE 24(9). [AB]
Conneau, A., Lample, G., Ranzato, M., Denoyer, L. & Jégou, H. (2018). Word translation without parallel data. ICLR. [SEC]
Cormack, G. & Grossman, M. (2016). Engineering quality and reliability in technology-assisted review. SIGIR. [AB]
Feldbauer, R. & Flexer, A. (2019). A comprehensive empirical comparison of hubness reduction in high-dimensional spaces. Knowledge and Information Systems 59(1). PMC7327987. [FT]
Hachey, B., Radford, W., Nothman, J., Honnibal, M. & Curran, J. (2013). Evaluating entity linking with Wikipedia. Artificial Intelligence 194, 130–150. [AB]
Jégou, H., Schmid, C., Harzallah, H. & Verbeek, J. (2010). Accurate image search using the contextual dissimilarity measure. IEEE TPAMI 32(1), 2–11. [AB]
Kanoulas, E., Dai, K., Pavlu, V. & Aslam, J. (2010). Score distribution models: assumptions, intuition, and robustness to score manipulation. SIGIR. [SEC]
Khattab, O. & Zaharia, M. (2020). ColBERT: efficient and effective passage search via contextualized late interaction over BERT. SIGIR. arXiv 2004.12832. [FT]
Korn, F. & Muthukrishnan, S. (2000). Influence sets based on reverse nearest neighbor queries. SIGMOD. [AB]
Krishnapuram, R. & Keller, J. (1993). A possibilistic approach to clustering. IEEE Trans. Fuzzy Systems 1(2). [SEC]
Kuzi, S., Shtok, A. & Kurland, O. (2016). Query expansion using word embeddings. CIKM. [AB]
Li, D. & Kanoulas, E. (2020). When to stop reviewing in technology-assisted reviews. ACM TOIS 38(4). [SEC]
Li, S., Park, S., Lee, I. & Bastani, O. (2024). TRAQ: trustworthy retrieval augmented question answering via conformal prediction. NAACL. [AB]
Lien, Y.-C., Cohen, D. & Croft, W. B. (2019). An assumption-free approach to the dynamic truncation of ranked lists. ICTIR. [AB]
Manmatha, R., Rath, T. & Feng, F. (2001). Modeling score distributions for combining the outputs of search engines. SIGIR. [AB]
Meng, C., Arabzadeh, N., Askari, A., Aliannejadi, M. & de Rijke, M. (2024). Ranked list truncation for large language model-based re-ranking. arXiv 2404.18185. [FT]
NVIDIA. Llama-Nemotron-Embed-1B-v2 model card, huggingface.co/nvidia/Llama-Nemotron-Embed-1B-v2. [FT]
Ozaki, K., Shimbo, M., Komachi, M. & Matsumoto, Y. (2011). Using the mutual k-nearest neighbor graphs for semi-supervised classification on natural language data. CoNLL, 154–162. [AB]
Papadakis, G., Koutrika, G., Palpanas, T. & Nejdl, W. (2014). Meta-blocking: taking entity resolution to the next level. IEEE TKDE 26(8), 1946–1960. [SEC]
Papadakis, G., Papastefanatos, G., Palpanas, T. & Koubarakis, M. (2016). Scaling entity resolution to large, heterogeneous data with enhanced meta-blocking. EDBT. [SEC]
Papadakis, G., Skoutas, D., Thanos, E. & Palpanas, T. (2020). Blocking and filtering techniques for entity resolution: a survey. ACM Computing Surveys 53(2). arXiv 1905.06167. [FT]
Qin, D., Gammeter, S., Bossard, L., Quack, T. & Van Gool, L. (2011). Hello neighbor: accurate object retrieval with k-reciprocal nearest neighbors. CVPR, 777–784. [AB]
Radovanović, M., Nanopoulos, A. & Ivanović, M. (2010). Hubs in space: popular nearest neighbors in high-dimensional data. JMLR 11, 2487–2531. [AB]
Rekabsaz, N., Lupu, M., Hanbury, A. & Zuccon, G. (2017). Exploration of a threshold for similarity based on uncertainty in word embedding. ECIR, 396–409. arXiv 1606.06086. [FT]
Roy, D., Paul, D., Mitra, M. & Garain, U. (2016). Using word embeddings for automatic query expansion. Neu-IR workshop at SIGIR. arXiv 1606.07608. [AB]
Satopää, V., Albrecht, J., Irwin, D. & Raghavan, B. (2011). Finding a "Kneedle" in a haystack: detecting knee points in system behavior. ICDCS Workshops, 166–171. [SEC]
Scheirer, W., Rocha, A., Micheals, R. & Boult, T. (2011). Meta-recognition: the theory and practice of recognition score analysis. IEEE TPAMI 33(8), 1689–1695. [AB]
Schnitzer, D., Flexer, A., Schedl, M. & Widmer, G. (2012). Local and global scaling reduce hubs in space. JMLR 13, 2871–2902. [AB]
Schubert, E. (2023). Stop using the elbow criterion for k-means and how to choose the number of clusters instead. SIGKDD Explorations 25(1), 36–42. [AB]
Shekkizhar, S. & Ortega, A. (2020). Graph construction from data by non-negative kernel regression. ICASSP. Long version arXiv 1910.09383. [FT]
Song, Z., Fang, J., Li, K., Xia, T. & Wang, C. (2026). Tail-aware adaptive-k: query-adaptive context selection for retrieval-augmented generation. arXiv 2606.11907. [AB]
Taguchi, C., Maekawa, S. & Bhutani, N. (2025). Efficient context selection for long-context QA: no tuning, no iteration, just adaptive-k. EMNLP. arXiv 2506.08479. [FT]
Tibshirani, R., Walther, G. & Hastie, T. (2001). Estimating the number of clusters in a data set via the gap statistic. JRSS B 63, 411–423. [SEC]
Wu, C., Zhang, R., Guo, J., Fan, Y., Lan, Y. & Cheng, X. (2021). Learning to truncate ranked lists for information retrieval. AAAI. arXiv 2102.12793. [FT]
Wu, L., Petroni, F., Josifoski, M., Riedel, S. & Zettlemoyer, L. (2020). Scalable zero-shot entity linking with dense entity retrieval. EMNLP. arXiv 1911.03814. [FT]
Zamani, H. & Croft, W. B. (2016). Embedding-based query language models. ICTIR, 147–156. [SEC]
Zelnik-Manor, L. & Perona, P. (2004). Self-tuning spectral clustering. NIPS. [SEC]
Zhong, Z., Zheng, L., Cao, D. & Li, S. (2017). Re-ranking person re-identification with k-reciprocal encoding. CVPR. arXiv 1701.08398. [FT]
Zhu, Q., Feng, J. & Huang, J. (2016). Natural neighbor: a self-adaptive neighborhood method without parameter K. Pattern Recognition Letters. [SEC]
