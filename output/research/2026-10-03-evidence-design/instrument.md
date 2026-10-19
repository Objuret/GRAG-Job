# The instrument on the real arrays — 2026-10-03

Measured: the fit lists, the text handles, the reach, a prototype of the evidence and where it
lands on the structure, for the ten 10smoke questions. Counts and statistics only. No gold, no
recall, no question or interpreter text, no model call, nothing written to the graph, no file
under `prod/` or `test/` changed.

## 0. What ran, and where each fact comes from

"run" = printed this session by the scripts in `scratch/`. "code" = read this session in the
named file. Nothing below comes from a docstring, a doc or a memory entry.

- Loaders (code): `test/arms/artefact_v4.py::prepare_over_corpus` (graph tag vectors `Tag.emb`,
  chunk description vectors `Chunk.desc_emb`, edges, topic = cos(tag, chunk description), the
  refit means `multikey_layer.values` from `scores_b24.npz`, the structure);
  `::_interpret` with `HERB_V4_OFFLINE=on` and `harness.chat.post` replaced by a function that
  raises; `test/arms/artefact_facet_joint.py::_query_cosines` (the pinned embedder, prefix
  `query: `). The questions came through `harness.orchestrator.load_chosen_questions` →
  `to_arm_question`, as the harness hands them to an arm; the gold fields were never read.
- Run: 10 questions, ten cache hits, 0 model calls. **100 query tags** (63 description-side, 37
  question-side; 9–12 a question; 11 repeated across the two lists). **N_tags = 16,609**
  eligible graph tags (16,654 less the 45 that equal a product name casefolded),
  **N_edges = 57,204**, **N = 4,808** chunks, 30 products (136–200 chunks, median 155.5), 302
  channels (1–32 chunks, median 7; 2,669 chunks sit in a channel). Eligible tags per chunk
  n_c: median 12, 1–48. 10,473 of the 16,609 tags (63%) sit on one chunk.
- Every table gives the median with (min – max): over the 100 query tags in A, B, D and the
  per-handle rows of E; over the 10 questions in C, F and the per-question rows of E.
  s is 1.4826·MAD of the list in question.
- Two checks of the code (run): one query tag recomputed without the library gives the same
  median, s, universal count and realness counts; its tag evidence by a plain loop over the
  57,204 edges equals the vectorised form (largest difference 0.0) — `scratch/crosscheck.py`.

## 1. Methods: literature, and what is construction

| step | literature | construction |
|---|---|---|
| bulk centre and spread, (i) | median and 1.4826·MAD (Hampel 1974; Rousseeuw & Croux 1993) | — |
| mode for (ii) | half-sample mode (Robertson & Cryer 1974; Bickel & Frühwirth 2006); kernel mode with Silverman's bandwidth (Silverman 1986) as a second estimate | — |
| "mirror" null, (ii) | the empirical null fitted where nulls dominate (Efron 2004, 2007) | spread from the lower half only, about the mode (the task's); the same about the median (this scratch) |
| best normal for the central 90% | truncated-normal maximum likelihood (Efron 2007) | — |
| fit of the central 90% | Kolmogorov distance (Kolmogorov 1933); reported as a distance, no p-value, the parameters being estimated from the same list (Lilliefors 1967) | restricting it to the central 90% (the task's) |
| universal threshold | b + s·√(2 ln N) (Donoho & Johnstone 1994) | — |
| realness m | N·p0(x)/rank(x) is the plug-in tail-area false discovery rate (Benjamini & Hochberg 1995; Storey 2002); its running minimum is the q-value (Storey & Tibshirani 2003) | m = 1 − min(1, N·p0/rank), without the running minimum, π0 = 1 (the task's) |
| local realness | 1 − f0(x)/f(x) (Efron, Tibshirani, Storey & Tusher 2001; Efron 2004) | added here beside the task's form |
| realness with no normal | #{x ≤ 2c − t} / #{x ≥ t} for a symmetric null (Barber & Candès 2015; Arias-Castro & Chen 2017) | taking the background as symmetric about the list's median (this scratch) |
| is there a break at the top | normalised spacings i·(x₍ᵢ₎ − x₍ᵢ₊₁₎) are iid under an exponential tail (Rényi 1953); the largest share of their sum has Fisher's exact distribution (Fisher 1929); the mean excess over a high threshold is the scale of that tail (Pickands 1975; Davison & Smith 1990) | using it on a fit list (this scratch) |
| spread of an estimator | bootstrap (Efron 1979) | — |
| random membership | permutation of the values over the chunks (Fisher 1935; Pitman 1937) | — |
| adding log positions | Fisher's sum of −ln p (Fisher 1932); for correlated terms the effective number H²/Σr (Brown 1975; the design effect of Kish 1965); eigenvalue counts (Li & Ji 2005; Galwey 2009) | w = 1/(row sum of the absolute correlation) (the task's) |
| −ln n_c | the best of n positions is n times as likely to be that good (Bonferroni; Šidák 1967; Tippett 1931) | its use on a path that also adds S_edge (the task's) |
| S_tag, S_edge, path value, chunk value, e, E0, node z | — | the task's prototype, coded as stated |

## 2. The estimators on synthetic lists, before the real ones (run, `scratch/selftest.py`)

40 lists of 16,609 values each; median (min – max).

| list | above universal | m > 0, MAD | m > 0.5, MAD | m > 0.9, MAD | m > 0.5, mode-mirror | m > 0.5, reflection about median | Fisher g p < 0.01 |
|---|---|---|---|---|---|---|---|
| pure normal | 0 (0 – 1) | 7,734 (525 – 16,240) | 0 (0 – 13) | 0 (0 – 1) | 1 (0 – 3,808) | 1 (0 – 19) | 1 of 40 |
| normal + 5 values at z 8–9 | 5 (5 – 6) | 6,931 | 9.5 (5 – 40) | 5 (5 – 8) | 10 (5 – 2,601) | 9.5 (5 – 40) | 40 of 40, break after rank 5 |
| normal + 1 value at z 11.6 | 1 (1 – 2) | 8,056 | 2 (1 – 7) | 1 (1 – 3) | 2 (1 – 4,119) | 2 (1 – 23) | 40 of 40, break after rank 1 |
| Student t, 6 df (heavy both sides) | 28 (18 – 40) | 8,590 | 492 (409 – 614) | 118 (90 – 149) | 432 (81 – 3,126) | 1 (0 – 34) | 0 of 40 |
| normal + 3% on a smooth exponential upper tail | 58 (44 – 87) | 13,640 | 704 (489 – 857) | 202 (144 – 238) | 1,097 (161 – 3,828) | 837 (642 – 974) | 1 of 40 |

The last synthetic list also gives skewness 0.76, KS of the central 90% against the MAD normal
0.020, 9.3 times the normal count above +3 s and a top-100 mean excess of 1.15 s.

## A. Fit lists: cos(query tag, every eligible graph tag) (run)

| quantity | median (min – max) |
|---|---|
| (i) centre: median cosine | 0.108 (0.029 – 0.219) |
| (i) spread: s = 1.4826·MAD | 0.029 (0.020 – 0.039) |
| (ii) centre: half-sample mode | 0.106 (0.022 – 0.217) |
| mode − median, in s | −0.037 (−0.451 – 0.202) |
| kernel mode − half-sample mode, in s | 0.014 (−0.267 – 0.260) |
| (ii) spread, lower half about the mode | 0.028 (0.018 – 0.038) |
| (ii) spread / (i) spread | 0.965 (0.672 – 1.13) |
| spread of the lower half about the median / of the upper half | 0.029 / 0.030 |
| skewness (third moment) | 0.71 (−0.27 – 2.01) |
| quartile skewness (Bowley) | 0.021 (−0.061 – 0.109) |
| excess kurtosis | 2.56 (0.55 – 11.6) |
| lowest tag, in s from the median | −4.31 (−5.56 – −2.73) |
| KS, central 90%: best-fitting normal | 0.011 (0.005 – 0.037) |
| KS, central 90%: median/MAD normal | 0.020 (0.010 – 0.046) |
| KS, central 90%: mode-mirror normal | 0.043 (0.005 – 0.237) |
| KS, lower half against the mode-mirror half-normal | 0.020 (0.006 – 0.055) |
| top-1 / top-10 / top-100 cosine | 0.369 / 0.303 / 0.233 |
| top-1 in z, MAD | 8.58 (4.67 – 14.3) |
| top-10 in z, MAD | 6.37 (3.97 – 10.5) |
| top-100 in z, MAD | 3.97 (2.54 – 6.48) |
| top-1 / top-10 / top-100 in z, mode-mirror | 9.25 (4.31 – 18.0) / 6.96 (3.66 – 14.9) / 4.19 (2.27 – 8.08) |
| universal threshold b + s·√(2 ln N_tags), z = 4.409: cosine | 0.240 (0.146 – 0.391) |
| tags above it, MAD | 67 (3 – 383) |
| tags above it, mode-mirror | 81 (0 – 852) |
| tags above it, median-mirror | 66 (0 – 543) |
| m > 0 / > 0.5 / > 0.9, MAD | 12,419 (1,116 – 16,518) / 834 (37 – 2,220) / 258 (14 – 1,293) |
| m > 0 / > 0.5 / > 0.9, mode-mirror | 14,293 (40 – 16,609) / 1,038 (26 – 8,274) / 364 (1 – 3,474) |
| m > 0 / > 0.5 / > 0.9, median-mirror | 9,776 (3,112 – 13,429) / 895 (30 – 2,636) / 294 (4 – 1,470) |
| m > 0.5 / > 0.9, reflection about the median (no normal) | 698 (0 – 2,846) / 176 (0 – 1,658) |
| tags above the reflection of the lowest tag | 74.5 (0 – 773) |
| local realness > 0.5 / > 0.9, MAD | 410 (19 – 1,255) / 158 (10 – 927) |
| m of the top-1 / of the top-10, MAD | 1.000 (0.975 – 1) / 1.000 (0.941 – 1) |
| tags with m > 0 below the centre, MAD | 5,680 (300 – 8,305); their largest m 0.010 (0.001 – 0.039) |
| observed / normal count above +2 s, +3 s, +4 s (MAD) | 2.08 / 11.1 (1.74 – 44.6) / 184 (17.1 – 1,063) |
| observed / normal count below −2 s, −3 s, −4 s (MAD) | 1.17 / 1.98 (0 – 7.18) / 3.80 (0 – 60.8) |
| top-100 mean excess over the 101st, in s | 1.06 (0.50 – 2.43); a normal list of this size: 0.32 |
| top-1 minus top-2, in s | 0.34 (0.002 – 3.74) |
| Fisher g on the top-100 spacings: p | 0.31 (6e-7 – 0.999); rank of the largest spacing 50 (3 – 100) |

Counts over the 100 query tags: no query tag has zero tags at m > 0.5 or m > 0.9 under either
normal null; 41 have more than 1,000 tags at m > 0.5 under the MAD null (50 under the
mode-mirror), 3 have more than 1,000 at m > 0.9 (18 under the mode-mirror). The running-minimum
form (q-value) gives 834 and 258.5 at 0.5 and 0.9, and m > 0 for all 16,609 tags.
The literal m is not monotone at the top by at most 0.012 (its maximum sits at rank 1–3).
Description-side and question-side tags read alike: top-1 z 8.62 and 8.52, m > 0.5 on 849 and
656 tags.

Resampling each list 100 times (bootstrap), the standard deviation of each estimator:

| estimator | sd, median (min – max) |
|---|---|
| median, in s | 0.009 (0.008 – 0.013) |
| s, relative | 0.009 (0.007 – 0.011) |
| half-sample mode, in s | 0.115 (0.058 – 0.203) |
| mode-mirror spread, relative to s | 0.063 (0.030 – 0.122) |

**Separation or continuum.** A break in the top 100 at p < 0.01 on 8 of the 100 lists (1 of
100 under an exponential tail; 1 of 40 on the synthetic normal lists), after ranks 6, 6, 14,
17, 19, 20, 20, 71; none after ranks 1–5. Over the 100 lists the top 100 lie a mean 1.06 s
above the 101st, the scale of an exponential tail and 3.3 times the 0.32 s of a normal list of
this size, and the best tag stands 0.34 s above the second. Every count of "exceptional" tags
is tens to hundreds and ranges over two orders of magnitude between query tags: 67 above the
universal threshold, 75 above the reflection of the lowest tag, 158 / 258 at realness 0.9
(local / tail-area), 410 / 834 at 0.5. The synthetic list built as a normal bulk with 3% of its
items on a smooth exponential upper tail gives 58, 704 and 202, skewness 0.76 and KS 0.020,
against the measured 67, 834 and 258, 0.71 and 0.020; the synthetic lists with one or five
planted matches give 1–5 above the universal threshold, 2–10 at m > 0.5, and a break at the
planted rank on 40 of 40.

**Which null estimator.** The median with 1.4826·MAD, on four measured grounds: its centre and
spread reproduce under resampling to 0.009 s and 0.9%, the half-sample mode to 0.115 s and the
mirror spread to 6.3%; the centre of the lists is symmetric (quartile skewness 0.021, lower-half
spread 0.029 against upper-half 0.030), so the lower half about the median gives the MAD spread
and the mode adds only its own noise; on pure-normal synthetic lists of the same size the MAD
null puts 0 values (at most 13) at m > 0.5 and the mode-mirror up to 3,808; on the real lists
the mode-mirror count at m > 0.5 is 0.12 to 5.6 times the MAD count for the same list. What
neither normal null has is a calibrated tail: below the centre, the side a match does not sit
on, the lists hold 1.98 times the normal count beyond 3 s and 3.8 times beyond 4 s (excess
kurtosis 2.56), so N·p0(x) is too small by that order before any match is counted. The
reflection about the median, which assumes no normal, gives 698 and 176 where the MAD normal
gives 834 and 258.

## B. Identity reference (run)

300 eligible graph tag names (seed 20261003, readable form: underscores as spaces, 300 distinct),
embedded with the query prefix through `_query_cosines`, against all stored tag vectors.

| quantity | value |
|---|---|
| cosine to its own stored vector | median 0.474, 5–95% 0.372 – 0.624, min 0.274, max 0.717 |
| own tag at rank 1 / within the first 10 | 85.7% / 99.3% (worst rank 18) |
| own tag in z of its list (MAD) | 11.6 (4.82 – 21.9) |
| own tag above the best other tag, in s | 1.84 (−1.88 – 10.7) |
| background median of an identity list | 0.114 (0.005 – 0.192) |
| tags above the universal threshold in an identity list | 69 (1 – 805) |
| m > 0.5 / > 0.9 in an identity list, MAD | 866 (2 – 2,575) / 304 (1 – 1,553) |
| local realness > 0.5 / > 0.9 | 420 (1 – 1,523) / 184 (1 – 1,142) |
| break in the top 100 at p < 0.01 | 17% of the 300 lists; after rank 1 on 4% |
| a query tag's top-1 between its background median (0) and the identity median (1) | 0.72 (0.34 – 1.18) |
| a query tag's top-10 on the same scale | 0.53 (0.24 – 1.07) |
| query tags whose top-1 reaches the identity median 0.474 / the identity 5% point 0.372 | 14 / 47 of 100 |

A list that holds one certain match gives counts of the size of a query tag's list (69, 866,
304 against 67, 834, 258); the certain match stands 1.84 s above the next tag, less than two
tail scales (1.04 s in these lists).

## C. Text handles: cos(text, the 4,808 chunk descriptions) (run)

For N = 4,808 the universal threshold is z = 4.118; the largest of 4,808 normal values has
median 3.63 and 99th percentile 4.60; a normal tail has a top-100 mean excess of 0.37 s.

| quantity | query description | raw question |
|---|---|---|
| centre: median cosine | 0.210 (0.136 – 0.260) | 0.184 (0.143 – 0.248) |
| spread s | 0.059 (0.051 – 0.068) | 0.062 (0.043 – 0.071) |
| mode-mirror spread / s | 0.99 (0.65 – 1.24) | 1.01 (0.76 – 1.26) |
| skewness | 0.17 (−0.51 – 0.59) | 0.17 (−0.42 – 1.80) |
| excess kurtosis | −0.04 (−0.29 – 0.74) | 0.26 (−0.23 – 5.42) |
| KS central 90%: best normal / MAD / mode-mirror (5% point of Kolmogorov 0.021) | 0.014 / 0.022 / 0.065 (0.022 – 0.276) | 0.019 / 0.026 / 0.050 (0.021 – 0.187) |
| top-1 in z, MAD | 3.75 (3.29 – 5.47) | 4.84 (3.42 – 10.4) |
| top-10 in z, MAD | 2.98 (2.27 – 3.91) | 3.48 (2.84 – 7.61) |
| top-100 in z, MAD | 2.14 (1.56 – 2.54) | 2.17 (1.87 – 4.63) |
| chunks above the universal threshold, MAD | 0 (0 – 8) | 3 (0 – 140) |
| m > 0 / > 0.5 / > 0.9, MAD | 3,293 / 13.5 (0 – 244) / 0 (0 – 54) | 2,220 / 21.5 (0 – 573) / 8 (0 – 315) |
| m > 0.5 / > 0.9, mode-mirror | 62 (0 – 2,646) / 3.5 (0 – 1,155) | 150 (0 – 1,959) / 24.5 (0 – 658) |
| m > 0.5 / > 0.9, reflection about the median | 132 (0 – 444) / 20.5 (0 – 155) | 98.5 (3 – 741) / 23 (0 – 396) |
| m of the top-1, MAD | 0.56 (0 – 1) | 0.99 (0 – 1) |
| observed / normal count above +3 s | 1.39 (0.15 – 9.24) | 2.70 (1.23 – 36.1) |
| top-100 mean excess, in s | 0.40 (0.30 – 0.70) | 0.52 (0.34 – 1.23) |
| break in the top 100 at p < 0.01 | 1 of 10 | 0 of 10 |

Per question, in the order of `data/10smoke.jsonl` (MAD null):

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| description: top-1 z | 3.53 | 5.48 | 3.52 | 4.12 | 3.32 | 3.81 | 4.26 | 3.69 | 4.33 | 3.29 |
| description: m of the top-1 | 0.02 | 1.00 | 0.00 | 0.91 | 0.00 | 0.66 | 0.95 | 0.45 | 0.96 | 0.00 |
| description: chunks at m > 0.5 | 0 | 244 | 0 | 49 | 0 | 3 | 168 | 24 | 48 | 0 |
| description: same, mode-mirror | 769 | 2,646 | 0 | 1,104 | 0 | 912 | 73 | 51 | 49 | 0 |
| question: top-1 z | 4.04 | 10.36 | 5.55 | 5.22 | 3.99 | 3.55 | 6.80 | 5.57 | 4.46 | 3.42 |
| question: m of the top-1 | 0.87 | 1.00 | 1.00 | 1.00 | 0.84 | 0.08 | 1.00 | 1.00 | 0.98 | 0.00 |
| question: chunks at m > 0.5 | 19 | 573 | 208 | 24 | 7 | 0 | 416 | 130 | 14 | 1 |

Spearman between the two texts' cosines over the 4,808 chunks: 0.78 (0.59 – 0.91).

## D. Reach (run)

| per query tag | MAD null | mode-mirror null |
|---|---|---|
| graph tags at m > 0.5 | 834 (37 – 2,220) | 1,038 (26 – 8,274) |
| chunks carrying at least one of them | 1,943 (123 – 3,174) | 2,120 (35 – 4,695) |
| share of those tags on exactly one chunk (all tags: 0.63) | 0.64 (0.51 – 0.79) | 0.64 (0.52 – 0.81) |
| graph tags above the universal threshold | 67 (3 – 383) | 81 (0 – 852) |
| chunks carrying at least one of those | 240 (5 – 1,003) | 308 (0 – 2,180) |
| chunks with a nonzero hit e_q(c) | 4,065 (1,523 – 4,629) | 4,133 (58 – 4,641) |

Chunks hit by query tags, per question (MAD null; under the mode-mirror null e > 0 from ≥3
query tags on 4,590 – 4,787 chunks and e > 1 from ≥3 on 1,486 – 2,645):

| question id | e > 0 from ≥1 | ≥2 | ≥3 query tags | e > 1 from ≥1 | ≥2 | ≥3 |
|---|---|---|---|---|---|---|
| ForecastForce::a::24 | 4,801 | 4,780 | 4,675 | 3,744 | 2,797 | 1,867 |
| ActionGenie::a::5 | 4,793 | 4,770 | 4,737 | 3,189 | 2,435 | 1,858 |
| ActionGenie::a::0 | 4,808 | 4,802 | 4,776 | 3,560 | 2,743 | 1,517 |
| CoachForce::a::5 | 4,797 | 4,789 | 4,663 | 3,585 | 3,229 | 2,059 |
| VizForce::a::16 | 4,785 | 4,767 | 4,730 | 2,968 | 2,357 | 1,815 |
| MonitorForce::a::16 | 4,801 | 4,774 | 4,659 | 3,732 | 2,612 | 1,609 |
| ActionGenie::a::7 | 4,805 | 4,796 | 4,771 | 3,625 | 3,081 | 2,185 |
| ActionGenie::a::1 | 4,807 | 4,793 | 4,768 | 3,543 | 2,977 | 1,885 |
| CoachForce::a::11 | 4,792 | 4,751 | 4,660 | 3,345 | 2,688 | 2,050 |
| PersonalizeForce::a::24 | 4,808 | 4,807 | 4,803 | 4,064 | 3,468 | 2,532 |

## E. The prototype of the evidence (run; scratch code only)

As stated in the task; m is the literal form of A under the null named; S_tag = ln(N_tags/rank),
S_edge = ln(N_edges/rank) of the weighted mean of the edge's five positions (the readings as
weights; no query tag has all five readings 0), path = m·(S_tag − ln n_c + S_edge) floored at 0,
chunk value = its best path, e = m*·ln(N/position), ties at the mid-rank.

The five position columns over the 57,204 edges, Spearman: temporal–activity 0.84,
why–concreteness 0.75, topic–activity 0.33, activity–concreteness 0.30, topic–temporal 0.26,
topic–concreteness 0.18, the other four between −0.18 and 0.06.

| e per handle | tag handle (100) | description (10) | raw question (10) |
|---|---|---|---|
| chunks with e > 0, MAD | 4,065 (1,523 – 4,629) | 3,292 (170 – 4,565) | 2,220 (332 – 4,376) |
| chunks with e > 0.1, MAD | 2,866 (468 – 3,463) | 830 (0 – 1,169) | 611 (12 – 1,349) |
| chunks with e > 1, MAD | 1,196 (153 – 1,656) | 76.5 (0 – 344) | 114 (11 – 600) |
| max e (ceiling ln 4,808 = 8.48), MAD | 8.48 (8.03 – 8.48) | 5.65 (0.002 – 8.48) | 8.39 (2.78 – 8.48) |
| sum of e (ceiling 4,808), MAD | 3,312 (626 – 4,221) | 490 (0.05 – 1,195) | 550 (48 – 1,936) |
| chunks with e > 0, mode-mirror | 4,133 (58 – 4,641) | 3,462 (49 – 4,807) | 2,818 (5 – 4,806) |
| sum of e, mode-mirror | 3,547 (193 – 4,617) | 566 (0.0005 – 3,978) | 805 (1.3 – 3,501) |

No handle is zero everywhere. The description's largest e is below 1 on 4 of the 10 questions
(MAD; 3 under the mode-mirror).

Inside a tag handle (MAD): of the 43,042 (4,586 – 56,898) paths whose tag has m > 0, 28,829 are
floored at 0. The winning path of a hit chunk has S_tag 2.78, S_edge 1.18, ln n_c 2.48 (medians),
and m* 0.43 (0.004 – 0.91); 1,914 (123 – 3,105) hit chunks have m* > 0.5. Over all hit chunks the
chunk value follows the tag position (Spearman with S_tag 0.93, with S_edge 0.03, with ln n_c
0.16); among the 50 highest chunks of a handle, which come through 27 (1 – 49) distinct tags,
Spearman with S_tag 0.20 (−0.42 – 0.70) and with S_edge 0.29 (−0.25 – 0.89).

| correlations and weights, per question | MAD null | mode-mirror null |
|---|---|---|
| handles | 12 (11 – 14) | same |
| tag–tag r: the question's median pair | 0.10 (0.04 – 0.31) | 0.11 (0.02 – 0.33) |
| tag–tag r: the question's largest pair | 0.999 (0.79 – 1.00) | 0.999 (0.79 – 1.00) |
| tag pairs with r > 0.5 / > 0.9, pooled over the ten | 99 / 19 of 454 | 101 / 18 of 454 |
| description – raw question r | 0.36 (−0.01 – 0.83) | 0.29 (−0.21 – 0.86) |
| tag – description r: median / largest of the question | 0.08 / 0.27 (0.02 – 0.54) | 0.08 / 0.33 (−0.03 – 0.54) |
| tag – raw question r: median of the question | 0.12 (0.01 – 0.43) | 0.11 (−0.01 – 0.44) |
| w of a tag handle: median / smallest / largest of the question | 0.24 / 0.21 / 0.51 | 0.25 / 0.21 / 0.52 |
| w of the description | 0.35 (0.23 – 0.86) | 0.35 (0.21 – 0.69) |
| w of the raw question | 0.35 (0.22 – 0.65) | 0.36 (0.21 – 0.83) |
| sum of w | 3.94 (2.82 – 5.74) | 4.03 (2.90 – 5.70) |
| H² / Σr (Brown; Kish) | 3.37 (2.68 – 5.82) | 3.56 (2.61 – 6.77) |
| eigenvalue counts: Li & Ji / Galwey | 8.5 / 8.1 | 8.5 / 8.2 |
| share of E0 from the tag handles | 0.966 (0.902 – 0.996) | 0.950 (0.803 – 1.000) |
| share from the description / the raw question | 0.017 / 0.019 | 0.022 / 0.027 |
| share from the tag handles among the 50 highest E0 | 0.90 (0.79 – 0.97) | 0.90 (0.78 – 1.00) |
| Spearman(n_c, mean tag e) | 0.28 (0.10 – 0.41) | 0.17 (0.005 – 0.32) |
| the same without the −ln n_c term | 0.42 (0.24 – 0.54) | 0.39 (0.24 – 0.50) |
| the same with the fits shuffled over the tags | 0.30 (0.22 – 0.39) | 0.21 (0.14 – 0.30) |
| shuffled, without the −ln n_c term | 0.54 (0.48 – 0.60) | 0.50 (0.46 – 0.56) |

Σw ≥ H²/Σ|r| by the harmonic–arithmetic mean inequality, and equals Brown's effective number
when the row sums are equal and no r is negative.

Three checks beside E (run, `scratch/extra_checks.py`):

- Tag position and edge standing inside a path: Spearman over the 57,204 edges −0.01
  (−0.23 – 0.34) per query tag; over the edges of the 834 best-fitting tags −0.07 (−0.39 – 0.31).
  Fit against the tag's number of chunks: 0.03 (−0.08 – 0.20).
- The readings and the edge standing: the 500 readings take 13 distinct values; their sum per
  query tag is 3.8 (2.0 – 4.7); the largest normalised weight exceeds the smallest by 0.14
  (0.03 – 0.50). Spearman between the edge standings of two query tags over all edges: 0.977
  (0.711 – 1), 5th percentile 0.868; with the equal-weight mean of the five positions: 0.986
  (0.823 – 0.999). The best 1% of edges of two query tags overlap by 74% (21 – 100%).
- The raw cosine across query tags: Spearman between a query tag's background median and its
  top-1 cosine 0.58, and its top-1 z 0.05. Within a question the query tags ordered by raw
  top-1 cosine and by top-1 z agree at Spearman 0.81 (0.10 – 0.97). The multikey sort's first
  key (code, `v4_multikey.multikey_order`: `floor((best over the question's rows − fit)/0.002)`)
  puts a query tag's best fit 58 levels (0 – 151) below the question's best; one 0.002 level is
  0.068 s (0.051 – 0.099).

## F. Structure from where the evidence lands (run)

E0(c) = Σ w·e over the question's handles; z = (mean over the node − μ)/(σ/√|n|). Random
membership: E0 shuffled over the chunks 2,000 times, the largest z over the 30 products and over
the 302 channels each time. A normal z would put the 99th percentile of that largest value at
3.40 (30 nodes) and 3.99 (302 nodes).

MAD null:

| question id | product z, top | second | top is the id's product | its rank | its rank, tag handles only | text handles only | random 99% | channel z, top | second | top's chunks | under the id's product | random 99% | channels above it |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ForecastForce::a::24 | 5.03 | 4.50 | no | 13 | 22 | 1 | 3.62 | 8.51 | 8.37 | 26 | no | 6.65 | 3 |
| ActionGenie::a::5 | 24.11 | 8.37 | yes | 1 | 1 | 1 | 3.49 | 9.02 | 8.88 | 6 | yes | 5.83 | 4 |
| ActionGenie::a::0 | 7.35 | 2.96 | yes | 1 | 22 | 1 | 3.52 | 5.41 | 4.18 | 11 | yes | 5.16 | 1 |
| CoachForce::a::5 | 6.84 | 3.45 | yes | 1 | 1 | 1 | 3.67 | 15.25 | 7.75 | 10 | yes | 8.51 | 1 |
| VizForce::a::16 | 3.49 | 3.48 | yes | 1 | 3 | 1 | 3.37 | 6.96 | 4.56 | 6 | yes | 5.64 | 1 |
| MonitorForce::a::16 | 11.06 | 6.97 | yes | 1 | 1 | 1 | 3.58 | 9.26 | 6.84 | 17 | yes | 6.28 | 2 |
| ActionGenie::a::7 | 19.36 | 2.79 | yes | 1 | 1 | 1 | 3.57 | 9.57 | 7.57 | 22 | yes | 6.39 | 3 |
| ActionGenie::a::1 | 6.67 | 3.49 | yes | 1 | 17 | 1 | 3.48 | 4.95 | 4.93 | 32 | no | 5.46 | 0 |
| CoachForce::a::11 | 5.73 | 2.04 | yes | 1 | 1 | 1 | 3.53 | 11.12 | 5.84 | 10 | yes | 7.17 | 1 |
| PersonalizeForce::a::24 | 11.96 | 5.63 | yes | 1 | 1 | 1 | 3.55 | 7.83 | 7.14 | 12 | yes | 5.82 | 7 |

| over the 10 questions | MAD null | mode-mirror null |
|---|---|---|
| product: top z | 7.10 (3.49 – 24.1) | 7.46 (3.32 – 24.7) |
| product: second z | 3.49 (2.04 – 8.37) | 3.76 (2.08 – 8.93) |
| the top product is the one in the id's prefix | 9 of 10 | 8 of 10 |
| the same from the tag handles alone / the text handles alone | 6 / 10 | 6 / 9 |
| top z from the tag handles alone / the text handles alone | 4.61 (3.17 – 15.5) / 23.8 (11.0 – 41.7) | 4.87 / 21.4 (3.92 – 40.9) |
| product: 99th percentile of the largest z under random membership | 3.54 (3.37 – 3.67) | 3.57 (3.51 – 3.68) |
| channel: top z | 8.76 (4.95 – 15.2) | 9.28 (4.32 – 15.1) |
| channel: second z | 6.99 (4.18 – 8.88) | 7.43 (3.94 – 8.86) |
| channel: 99th percentile of the largest z under random membership | 6.05 (5.16 – 8.51) | 5.96 (5.31 – 8.16) |
| questions with at least one channel above that percentile | 9 of 10 | 8 of 10 |
| the top channel lies under the id's product | 8 of 10 | 7 of 10 |

## G. What breaks the principle, with the number

1. **No separable background on the tag side.** A break in the top 100 on 8 of 100 lists and
   never after ranks 1–5; realness 1 for hundreds: m > 0.9 on 258 tags (14 – 1,293), m > 0.5 on
   834 (37 – 2,220), more than 1,000 tags at m > 0.5 for 41 of the 100 query tags. A list that
   holds one certain match gives 304 and 866.
2. **m > 0 is not "real".** The literal m is positive wherever the list's tail share exceeds
   the null's: on 12,419 of 16,609 tags (1,116 – 16,518), 5,680 of them below the centre; on
   pure-normal synthetic lists on 525 – 16,240. Through it a tag handle gives e > 0 to 4,065 of
   the 4,808 chunks (1,523 – 4,629), and ≥3 query tags hit 4,659 – 4,803 chunks of every
   question; e > 1 from ≥3 query tags on 1,517 – 2,532.
3. **The mode-mirror null is not stable.** The mode's bootstrap sd is 0.115 s against 0.009 s
   for the median; on pure-normal lists it calls up to 3,808 values real; on the description
   handle its counts at m > 0.5 are 769, 2,646, 0, 1,104, 0, 912, 73, 51, 49, 0 where the MAD
   null gives 0, 244, 0, 49, 0, 3, 168, 24, 48, 0.
4. **The normal tail is wrong on the tag lists.** Below the centre the lists hold 1.98 times
   the normal count beyond 3 s and 3.8 times beyond 4 s; above, 11.1 and 184 times.
5. **The description handle sits at the level of its own noise.** Its best chunk is at z 3.75
   (3.29 – 5.47); the largest of 4,808 normal values has median 3.63; the universal threshold
   is 4.12 and no chunk passes it on 6 of 10 questions; no chunk has m > 0.5 on 4 of 10; its
   top-100 tail is a normal tail (0.40 s against 0.37 s). Tag lists: top-1 at z 8.58.
6. **The two families land on different scales.** A tag handle's e sums to 3,312, the
   description's to 490, the raw question's to 550; 96.6% (90.2 – 99.6%) of E0 comes from the
   tag handles, 1.7% from the description.
7. **The handles are not independent.** 11 of the 100 query tags repeat across the two lists;
   19 of the 454 tag pairs have r > 0.9 and 99 have r > 0.5; description against raw question
   r 0.36 (up to 0.83), their cosines Spearman 0.78. Σw is 3.94 for 12 handles.
8. **−ln n_c does not remove the tag count.** Spearman between n_c and the mean tag evidence
   0.28 (0.42 without the term); 0.30 with the fits shuffled over the tags.
9. **The edge standing is nearly the same for every query tag.** Spearman 0.977 between two
   query tags' standings, 0.986 with the equal-weight mean of the five positions; the readings
   take 13 values and sum to 3.8 of 5.
10. **The channel z is not a normal deviate.** Random membership puts the 99th percentile of
    the largest channel z at 5.16 – 8.51, against 3.99; the product z is calibrated
    (3.37 – 3.67 against 3.40). VizForce::a::16: top product 3.49, second 3.48.

## What the data support and what they do not

Support:

- A background per handle that can be estimated: median and MAD, stable to 0.009 s, the
  central 90% within a Kolmogorov distance of 0.020 of it (best normal 0.011), 0 values (at
  most 13) at m > 0.5 on synthetic noise.
- Reading a fit against its own list rather than as a raw cosine: across query tags the
  background median runs 0.029 – 0.219 and s 0.020 – 0.039; the raw top-1 cosine follows the
  background (Spearman 0.58), the top-1 z does not (0.05); the identity cosine itself runs
  0.274 – 0.717.
- Adding the tag position and the edge standing inside a path: their Spearman is −0.01 at the
  median (−0.23 – 0.34 over query tags), and at the head of a handle both move the chunk value
  (0.20 and 0.29).
- The weights: Σw 3.94 against Brown's effective number 3.37 for the same correlations.
- The product read off the evidence: z calibrated under random membership; the id's product on
  top on 9 of 10 (from the text handles alone 10 of 10, from the tag handles alone 6 of 10).

Do not support:

- "Real or background" as a split of the tags (G1), the literal m > 0 as the gate (G2), the
  mode-mirror null (G3), the normal tail as a probability (G4).
- One realness rule for both families: it is 1 for hundreds of tags and near 0 for the
  description on 4 of 10 questions (G5, G6).
- Independence of the handles as written by the querytagger (G7).
- −ln n_c as the whole correction for the tag count (G8).
- The edge standing as a query-relative position (G9).
- The z of a channel as stated (G10).

## Not verified

- Whether a tag or chunk with high realness leads to an answering chunk: no gold was opened and
  no recall computed.
- Whether a question's text names the product of its id prefix: the text was not inspected.
- Ten questions, 100 query tags, one cached interpretation each; no gold100; the spread under
  a re-asked interpretation is not measured.
- One seed: 300 identity tags, 100 bootstrap resamples per list, 2,000 membership shuffles per
  question, one shuffle of the fits per query tag.
- Which build wrote the live `Tag.emb`, and from which text form; the identity probes used
  `test/graph/db.py::_readable`. (Measured afterwards, section H: the passage role reproduces
  the stored tag vectors to cosine 0.991.)
- Fisher's g assumes an exponential tail under no break; its false-positive rate was checked on
  synthetic lists only (1 of 40 at p < 0.01).
- π0 = 1 in m, as stated in the task; E and F were not run under the reflection null or the
  local form.
- 0.002 as the embedder's resolution is the constant in `artefact_v4.py`, not re-measured.

## Files

- `output/research/2026-10-03-evidence-design/instrument.md` — this file.
- `scratch/collect.py` — the arrays (numbers and ids only) through the arm's loaders; 296 s;
  writes `evidence_arrays.npz` to the folder named by `EVID_CACHE` (default: the session
  scratchpad, outside the repo).
- `scratch/instrument_lib.py` — the estimators. `scratch/selftest.py`, `selftest.out.txt` — the
  synthetic lists. `scratch/analyse.py` → `scratch/results.json` (A–F). `scratch/extra_checks.py`
  → `scratch/extra_results.json`. `scratch/crosscheck.py`. `scratch/make_tables.py`.

## References

Arias-Castro, E. & Chen, S. (2017). Distribution-free multiple testing. *Electronic Journal of Statistics* 11, 1983–2001.
Barber, R. F. & Candès, E. J. (2015). Controlling the false discovery rate via knockoffs. *Annals of Statistics* 43, 2055–2085.
Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate. *JRSS B* 57, 289–300.
Bickel, D. R. & Frühwirth, R. (2006). On a fast, robust estimator of the mode. *Computational Statistics & Data Analysis* 50, 3500–3530.
Brown, M. B. (1975). A method for combining non-independent, one-sided tests of significance. *Biometrics* 31, 987–992.
Davison, A. C. & Smith, R. L. (1990). Models for exceedances over high thresholds. *JRSS B* 52, 393–442.
Donoho, D. L. & Johnstone, I. M. (1994). Ideal spatial adaptation by wavelet shrinkage. *Biometrika* 81, 425–455.
Efron, B. (1979). Bootstrap methods: another look at the jackknife. *Annals of Statistics* 7, 1–26.
Efron, B. (2004). Large-scale simultaneous hypothesis testing: the choice of a null hypothesis. *JASA* 99, 96–104.
Efron, B. (2007). Size, power and false discovery rates. *Annals of Statistics* 35, 1351–1377.
Efron, B., Tibshirani, R., Storey, J. D. & Tusher, V. (2001). Empirical Bayes analysis of a microarray experiment. *JASA* 96, 1151–1160.
Fisher, R. A. (1929). Tests of significance in harmonic analysis. *Proceedings of the Royal Society A* 125, 54–59.
Fisher, R. A. (1932). *Statistical Methods for Research Workers*, 4th ed. Oliver & Boyd.
Fisher, R. A. (1935). *The Design of Experiments*. Oliver & Boyd.
Galwey, N. W. (2009). A new measure of the effective number of tests. *Genetic Epidemiology* 33, 559–568.
Hampel, F. R. (1974). The influence curve and its role in robust estimation. *JASA* 69, 383–393.
Kish, L. (1965). *Survey Sampling*. Wiley.
Kolmogorov, A. (1933). Sulla determinazione empirica di una legge di distribuzione. *Giornale dell'Istituto Italiano degli Attuari* 4, 83–91.
Li, J. & Ji, L. (2005). Adjusting multiple testing in multilocus analyses using the eigenvalues of a correlation matrix. *Heredity* 95, 221–227.
Lilliefors, H. W. (1967). On the Kolmogorov–Smirnov test for normality with mean and variance unknown. *JASA* 62, 399–402.
Pickands, J. (1975). Statistical inference using extreme order statistics. *Annals of Statistics* 3, 119–131.
Pitman, E. J. G. (1937). Significance tests which may be applied to samples from any populations. *Supplement to the JRSS* 4, 119–130.
Rényi, A. (1953). On the theory of order statistics. *Acta Mathematica Academiae Scientiarum Hungaricae* 4, 191–231.
Robertson, T. & Cryer, J. D. (1974). An iterative procedure for estimating the mode. *JASA* 69, 1012–1016.
Rousseeuw, P. J. & Croux, C. (1993). Alternatives to the median absolute deviation. *JASA* 88, 1273–1283.
Šidák, Z. (1967). Rectangular confidence regions for the means of multivariate normal distributions. *JASA* 62, 626–633.
Silverman, B. W. (1986). *Density Estimation for Statistics and Data Analysis*. Chapman & Hall.
Storey, J. D. (2002). A direct approach to false discovery rates. *JRSS B* 64, 479–498.
Storey, J. D. & Tibshirani, R. (2003). Statistical significance for genomewide studies. *PNAS* 100, 9440–9445.
Tippett, L. H. C. (1931). *The Methods of Statistics*. Williams & Norgate.

---

# H. Follow-up: the query tags and the query description in the passage role

The coordinator's question after A–G: the arm embeds the query side in the query role, the graph
side is stored in the passage role; embed the query tags and the query description in the
passage role ("symmetric") and redo A, B, C, F, and measure the exact chance correction for the
tag count. Same rules; the raw question stays in the query role. "Asymmetric" below is the
query role, as the arm runs and as A–G measured.

## H.0 What ran, and the role of the stored vectors

- Code: `test/graph/reembed_herb_eval.py` is the one file under `test/graph/` with a statement
  that sets `Tag.emb` or `Chunk.desc_emb` (`SET t.emb`, `SET c.desc_emb`); both vectors come
  from `_embed(…, "passage")`, the tag as `_readable(name)` (line 51), the description text as
  it is (line 83). Whether that script wrote the live graph's vectors is not in the code.
  `artefact_facet_joint._query_cosines` embeds with `'query'` (line 304).
- Run, the tags: the 300 identity names of B re-embedded in the passage role reach their own
  stored vector at cosine **0.991** (5–95% 0.985 – 0.993, min 0.975, max 0.995; 94 of 300 below
  0.99); in the query role 0.474. The stored tag vectors are passage-role vectors, reproduced by
  this machine's embedder to 0.991, not to 1.000. None of the 300 names differs from its readable
  form; 63 of the 16,609 eligible names do.
- The stored chunk descriptions: code only. Their texts are not in the graph and were not
  re-embedded.
- Run: the 100 query tags and the 10 descriptions embedded with the prefix `passage: ` through a
  copy of `_query_cosines` whose one change is the role (`scratch/collect_symmetric.py`). The
  same copy in the query role returns the first collection's arrays for the first question
  (largest difference 0.0). 0 model calls; nothing written outside this folder.
- Definitions for the top of a list (construction of this scratch on Rényi 1953): normalised
  spacing after rank i, D_i = i·(x₍ᵢ₎ − x₍ᵢ₊₁₎); tail scale = the mean D_i over ranks 101–200;
  the gap the tail predicts after rank i = scale/i; a **clear break** after rank i: D_i/scale
  above 9.64, the 99th percentile of the largest of 100 such ratios under an exponential tail
  (simulated, 200,000 draws; the largest of 50 has median 4.32 and 99th percentile 8.86); the
  **rank-1 test**: D_1/scale > ln 100 = 4.61 (probability 0.01 under an exponential tail).
- The detector on synthetic lists first (`scratch/selftest_gaps.py`, 200 lists of 16,609 each):
  a clear break on 2 pure-normal lists, on 3 lists with a smooth exponential tail, on 25
  Student-t(6) lists; with the 5 (20) best lifted 3 s above a smooth tail on 200 of 200, at rank
  5 (20); with the single best lifted 3 s on 0 of 200, lifted 6 s on 7 — hence the rank-1 test.

## A′. Fit lists (run; 100 query tags, median (min – max))

| quantity | asymmetric (query role) | symmetric (passage role) |
|---|---|---|
| bulk centre: median cosine | 0.108 (0.029 – 0.219) | 0.735 (0.632 – 0.780) |
| bulk spread s | 0.029 (0.020 – 0.039) | 0.056 (0.040 – 0.071) |
| spread of the upper half / of the lower half, over s | 1.02 / 0.98 | 0.90 / 1.15 |
| skewness | 0.71 (−0.27 – 2.01) | −1.06 (−1.31 – −0.46) |
| excess kurtosis | 2.56 (0.55 – 11.6) | 1.95 (1.00 – 2.68) |
| KS central 90%: best normal / MAD normal | 0.011 / 0.020 | 0.022 / 0.049 |
| observed / normal count above +3 s | 11.1 (1.74 – 44.6) | 0.09 (0 – 3.52) |
| observed / normal count below −3 s | 1.98 (0 – 7.18) | 18.9 (9.28 – 25.8) |
| top-1 / top-10 / top-100 cosine | 0.369 / 0.303 / 0.233 | 0.932 (0.801 – 0.995) / 0.888 / 0.847 |
| top-1 z | 8.58 (4.67 – 14.3) | 3.42 (2.09 – 7.23) |
| top-10 z | 6.37 (3.97 – 10.5) | 2.63 (1.97 – 4.38) |
| top-100 z | 3.97 (2.54 – 6.48) | 1.96 (1.70 – 2.89) |
| the same in spreads of the upper half: top-1 / 10 / 100 | 8.40 / 6.27 / 3.80 | 3.78 (2.36 – 7.63) / 2.92 / 2.19 |
| tags above the universal threshold (z 4.409) | 67 (3 – 383) | 0 (0 – 9) |
| m > 0.5 / m > 0.9, MAD null | 834 / 258 | 0 (0 – 198) / 0 (0 – 45) |
| tail scale, in s | 0.89 (0.42 – 2.86) | 0.28 (0.15 – 0.79) |
| mean spacing of ranks 1–50 over the tail scale | 1.04 (0.24 – 4.18) | 1.03 (0.44 – 1.99) |
| gap after rank 1, in s | 0.34 (0.002 – 3.74) | 0.22 (0.001 – 1.69) |
| gap after rank 1 over the gap the tail predicts | 0.35 (0.004 – 4.17) | 0.59 (0.003 – 5.02) |
| largest gap between consecutive tags in the top 50, in s | 0.83 (0.24 – 3.77) | 0.27 (0.03 – 1.69) |
| the rank it follows | 2 (1 – 41) | 2 (1 – 20) |
| the gap the tail predicts there, in s | 0.38 (0.02 – 2.86) | 0.19 (0.02 – 0.79) |
| largest gap over the predicted | 1.88 (0.14 – 30.9) | 1.58 (0.23 – 9.43) |
| largest normalised spacing in the top 50 over the tail scale (exponential tail: median 4.32, 99% 8.86) | 5.00 (1.71 – 30.9) | 4.30 (1.58 – 9.43) |
| lists with a clear break in the top 100 | 12 | 0 |
| tags above the first clear break | 6, 6, 14, 15, 15, 17, 18, 19, 19, 28, 41, 71 | — |
| lists with a clear break by the top-50 threshold (8.86) | 13 | 1, after rank 2 |
| Fisher g on the top-100 spacings, p < 0.01 | 8 lists (after 6, 6, 14, 17, 19, 20, 20, 71) | 0 lists |
| lists whose rank 1 passes the rank-1 test | 0 | 2 |

The identity level as an absolute mark (B, B′: the cosine of a graph tag's own name to its
vector):

| quantity | asymmetric | symmetric |
|---|---|---|
| identity cosine: minimum / median | 0.274 / 0.474 | 0.975 / 0.991 |
| query tags with a graph tag at or above the identity minimum | 86 of 100 | 30 of 100 (24 with one such tag, 6 with two) |
| graph tags at or above it, per query tag | 28 (0 – 1,458) | 0 (0 – 2) |
| step from the last such tag down to the next (80 and 30 lists): in cosine | 0.002 (0.0001 – 0.075) | 0.025 (0.015 – 0.091) |
| the same in s | 0.07 (0.002 – 2.34) | 0.45 (0.26 – 1.69) |
| the same over the gap the tail predicts | 1.78 (0.22 – 22.9) | 1.33 (0.51 – 9.43); above ln 100 on 3 of the 30 |
| top-1 cosine of the query tags with no tag at that level | 0.243 (0.211 – 0.274), 14 tags | 0.917 (0.801 – 0.970), 70 tags |
| top-1 between the background median (0) and the identity median (1) | 0.72 (0.34 – 1.18) | 0.76 (0.47 – 1.01) |

Do the two modes pick the same tags (per query tag):

| quantity | median (min – max) |
|---|---|
| tags shared by the two top-100 sets | 42 (4 – 67) |
| tags shared by the two top-10 sets | 4 (0 – 8) |
| the top-1 is the same tag | on 31 of 100 lists |
| rank of the symmetric top-1 in the asymmetric list | 3.5 (1 – 216) |
| rank of the asymmetric top-1 in the symmetric list | 5 (1 – 15,121) |
| Spearman of the two fits over all 16,609 tags | 0.66 (0.43 – 0.84) |
| Spearman over the asymmetric top 100 | 0.31 (−0.23 – 0.68) |
| Spearman over the union of the two top-100 sets (158 tags, 133 – 196) | −0.11 (−0.64 – 0.44) |

## B′. Identity (run; 300 graph tag names, readable form)

| quantity | asymmetric (B) | symmetric |
|---|---|---|
| cosine to the own stored vector | 0.474 (0.274 – 0.717) | 0.991 (0.975 – 0.995) |
| own tag at rank 1 | 85.7% (worst rank 18) | 100% |
| own tag in z of its list | 11.6 (4.82 – 21.9) | 5.00 (2.99 – 13.8) |
| best other tag, cosine | — | 0.938 (0.772 – 0.993) |
| own tag above the best other, in s | 1.84 (−1.88 – 10.7) | 0.95 (0.008 – 6.05) |
| gap after rank 1 over the gap the tail predicts | 1.91 (0 – 14.8) | 2.68 (0.005 – 14.2) |
| lists passing the rank-1 test | 69 of 300 | 64 of 300 |
| lists with a clear break in the top 100 / after rank 1 | 82 / 18 | 38 / 9 |
| background median; s | 0.114; 0.032 | 0.723 (0.524 – 0.789); 0.054 |
| tags above the universal threshold | 69 (1 – 805) | 1 (0 – 133) |
| m > 0.5 / m > 0.9, MAD null | 866 / 304 | 2 (0 – 1,470) / 1 (0 – 514) |

## C′. The query description against the 4,808 chunk descriptions (run; 10 questions)

The largest of 4,808 normal values: median 3.63, 99th percentile 4.60; universal threshold
z = 4.118; a normal list's top-100 mean excess 0.37 s.

| quantity | asymmetric (query role) | symmetric (passage role) |
|---|---|---|
| bulk centre: median cosine | 0.210 (0.136 – 0.260) | 0.243 (0.158 – 0.291) |
| bulk spread s | 0.059 (0.051 – 0.068) | 0.058 (0.049 – 0.065) |
| skewness; excess kurtosis | 0.17; −0.04 | 0.24; 0.02 |
| KS central 90%: best normal / MAD normal | 0.014 / 0.022 | 0.012 / 0.025 |
| top-1 / top-10 / top-100 cosine | 0.463 / 0.408 / 0.337 | 0.483 (0.356 – 0.552) / 0.435 / 0.367 |
| top-1 z | 3.75 (3.29 – 5.47) | 3.96 (3.57 – 5.26) |
| top-10 z | 2.98 (2.27 – 3.91) | 3.12 (2.62 – 3.85) |
| top-100 z | 2.14 (1.56 – 2.54) | 2.16 (1.76 – 2.59) |
| top-1 in spreads of the upper half | 3.85 (3.41 – 5.12) | 3.75 (3.63 – 4.88) |
| top-1 z per question | 3.53, 5.48, 3.52, 4.12, 3.32, 3.81, 4.26, 3.69, 4.33, 3.29 | 3.99, 5.26, 3.93, 3.74, 3.60, 3.89, 4.03, 5.08, 4.67, 3.57 |
| questions whose top-1 z is above 4.60 | 1 | 3 |
| chunks above the universal threshold | 0 (0 – 8) | 0 (0 – 6) |
| the same per question | 0, 8, 0, 1, 0, 0, 3, 0, 1, 0 | 0, 2, 0, 0, 0, 0, 0, 6, 4, 0 |
| questions with none above it | 6 | 7 |
| m > 0.5 / m > 0.9, MAD null | 13.5 (0 – 244) / 0 (0 – 54) | 25.5 (0 – 370) / 0 (0 – 42) |
| top-100 mean excess, in s | 0.40 (0.30 – 0.70) | 0.43 (0.35 – 0.70) |
| lists with a clear break in the top 100 | 1 (after rank 54) | 0 |

Between the two roles over the 4,808 chunks: Spearman 0.89 (0.72 – 0.94); the two top-100 sets
share 64 chunks (36 – 76), the two top-10 sets 6 (2 – 7). Spearman of the description's cosines
with the raw question's (query role): 0.78 (0.59 – 0.91) asymmetric, 0.60 (0.27 – 0.73)
symmetric. The raw question, unchanged: top-1 z 4.84 (3.42 – 10.4).

## The exact chance correction for the tag count (run)

Per query tag and chunk, as the coordinator states it: S_tag_i = ln(N_tags/rank_i) for each of
the chunk's eligible tags, S_edge_i as in E, v = max_i (S_tag_i + S_edge_i),
p_c = 1 − Π_i (1 − min(1, e^(−(v − S_edge_i)))), evidence −ln p_c; no realness gate. ρ is the
Spearman over the 4,808 chunks between n_c and the evidence averaged over the question's tag
handles; median (min – max) over the 10 questions. "Shuffled": the fit list shuffled over the
tags.

| chunk tag evidence | asymmetric: observed | shuffled | symmetric: observed | shuffled |
|---|---|---|---|---|
| best path v, no correction | 0.22 (0.03 – 0.28) | 0.26 (0.23 – 0.28) | 0.17 (−0.03 – 0.31) | 0.26 (0.23 – 0.30) |
| v − ln n_c | −0.18 (−0.34 – −0.10) | −0.20 (−0.23 – −0.17) | −0.28 (−0.39 – −0.15) | −0.20 (−0.23 – −0.14) |
| exact, −ln p_c | **0.04** (−0.22 – 0.12) | **0.01** (−0.04 – 0.06) | **−0.07** (−0.24 – 0.09) | **0.005** (−0.06 – 0.11) |
| fit only: the best S_tag, no correction | 0.51 (0.28 – 0.64) | 0.76 (0.73 – 0.77) | 0.42 (0.21 – 0.61) | 0.76 (0.72 – 0.78) |
| fit only, exact: p = 1 − (1 − e^(−v))^n_c | −0.03 (−0.21 – 0.13) | 0.01 (−0.04 – 0.09) | −0.07 (−0.24 – 0.11) | 0.01 (−0.07 – 0.14) |
| the chunk's best fit as a cosine | 0.51 (0.29 – 0.64) | 0.74 (0.70 – 0.76) | 0.44 (0.20 – 0.62) | 0.78 (0.74 – 0.80) |
| earlier (E, MAD null): the gated e with −ln n_c | 0.28 (0.10 – 0.41) | 0.30 (0.22 – 0.39) | — | — |

Per handle (100 handles) the exact evidence gives −0.08 (−0.35 – 0.23) observed and 0.004
(−0.11 – 0.14) shuffled in the asymmetric mode, −0.14 (−0.38 – 0.22) and 0.004 (−0.11 – 0.12)
in the symmetric.

Checks of the formula: by a plain loop over the chunks against the vectorised form, largest
difference 6e-13 (`scratch/crosscheck_symmetric.py`); with an independent exponential S_tag
drawn for every edge (50 draws) p_c is uniform to a Kolmogorov distance of 0.012, the mean
evidence is 1.000 and ρ(n_c, evidence) is 0.0002 (−0.028 – 0.039); with the fits shuffled over
the tags p_c is uniform to 0.031 (0.011 – 0.097) asymmetric and 0.030 (0.013 – 0.096) symmetric,
and the mean evidence is 0.99 (0.89 – 1.27) and 1.00 (0.89 – 1.23). Mean evidence with the
observed fits: 0.93 (0.61 – 1.49) asymmetric, 1.02 (0.70 – 1.70) symmetric.

What the exact value keeps (per handle, Spearman over the chunks): with the fit-only exact
value 0.82 (0.72 – 0.92) in both modes; with the chunk's best edge standing −0.04
(−0.35 – 0.47) asymmetric and −0.26 (−0.49 – 0.19) symmetric, where the uncorrected best path
has 0.64 (0.40 – 0.81) and 0.52 (0.35 – 0.70).

## F′. Product enrichment by family, plain standardised standings (run)

Evidence per handle and chunk: a text handle's value is its cosine, a tag handle's value the
best fit among the chunk's eligible tags; z against the median and 1.4826·MAD of that value
over the 4,808 chunks; positive part. No realness gate. Weights w = 1/(row sum of |r|) over
the question's handles as in E; node z and random membership as in F. Taking a tag handle's
chunk-level value as the best fit of the chunk's tags is this scratch's reading of "chunk
level"; two other readings are in the lower rows. The raw question is in the query role in
both columns.

| quantity | asymmetric | symmetric |
|---|---|---|
| tag handles alone: top z | 6.84 (2.55 – 17.8) | 4.35 (2.30 – 9.44) |
| tag handles alone: second z | 3.55 (2.33 – 6.99) | 2.98 (1.66 – 5.33) |
| tag handles alone: the id's product on top | 6 of 10 | 5 of 10 |
| tag handles alone: rank of the id's product | 1 (1 – 17) | 1.5 (1 – 17) |
| tag handles alone: 99% of the largest z under random membership | 3.51 (3.32 – 3.67) | 3.46 (3.36 – 3.69) |
| text handles alone (description + raw question): top z | 19.5 (10.6 – 39.6) | 18.8 (10.5 – 38.5) |
| text handles alone: second z | 6.14 (2.55 – 21.9) | 6.58 (3.05 – 21.9) |
| text handles alone: the id's product on top | 10 of 10 | 10 of 10 |
| text handles alone: 99% under random membership | 3.57 (3.41 – 3.67) | 3.61 (3.46 – 3.76) |
| description alone: top z / second z | 7.43 / 5.30 | 7.05 / 4.74 |
| description alone: the id's product on top; its rank | 4 of 10; 2 (1 – 29) | 4 of 10; 4.5 (1 – 28) |
| raw question alone: top z / second z; the id's product on top | 24.9 / 5.85; 10 of 10 | the same vector |
| all handles: top z / second z; the id's product on top | 7.90 / 3.32; 9 of 10 | 7.66 / 3.33; 9 of 10 |
| tag handles, other reading: the best tag's z in the fit list, positive part | 5.77 / 3.37; 6 of 10 | 3.58 / 2.60; 6 of 10 |
| tag handles, other reading: −ln p_c, z over the chunks, positive part | 4.62 / 3.36; 6 of 10 | 4.12 / 2.75; 4 of 10 |
| tag handles summed without weights (the three readings) | 6 / 6 / 6 of 10 | 6 / 5 / 3 of 10 |
| ρ(n_c, the tag part of the evidence) | 0.43 (0.32 – 0.56) | 0.39 (0.26 – 0.54) |
| r between the description's and the raw question's evidence | 0.76 (0.44 – 0.89) | 0.52 (0.22 – 0.71) |

Per question (tag handles alone: top z, second z, rank of the id's product; text handles alone
the same; rank of the id's product from the description alone):

| question id | asym tags | asym text | asym description | sym tags | sym text | sym description |
|---|---|---|---|---|---|---|
| ForecastForce::a::24 | 4.04, 3.74, 17 | 12.9, 7.91, 1 | 3 | 2.30, 2.30, 17 | 12.3, 8.57, 1 | 3 |
| ActionGenie::a::5 | 17.8, 4.15, 1 | 39.6, 21.9, 1 | 1 | 9.44, 5.33, 1 | 38.5, 21.9, 1 | 1 |
| ActionGenie::a::0 | 2.55, 2.36, 15 | 19.5, 7.44, 1 | 29 | 2.63, 2.32, 6 | 19.1, 7.42, 1 | 28 |
| CoachForce::a::5 | 7.34, 3.67, 1 | 13.3, 2.55, 1 | 2 | 6.77, 4.07, 1 | 12.5, 3.05, 1 | 8 |
| VizForce::a::16 | 3.23, 2.44, 2 | 19.9, 3.67, 1 | 2 | 2.90, 2.67, 6 | 19.5, 3.86, 1 | 6 |
| MonitorForce::a::16 | 7.72, 6.99, 1 | 14.7, 4.85, 1 | 1 | 3.57, 3.49, 2 | 15.7, 5.73, 1 | 1 |
| ActionGenie::a::7 | 11.6, 3.43, 1 | 33.9, 14.2, 1 | 1 | 5.12, 3.30, 1 | 32.9, 14.1, 1 | 1 |
| ActionGenie::a::1 | 2.66, 2.33, 14 | 19.4, 8.29, 1 | 27 | 3.03, 1.66, 7 | 18.6, 8.43, 1 | 27 |
| CoachForce::a::11 | 6.34, 2.58, 1 | 10.6, 2.83, 1 | 9 | 7.40, 2.17, 1 | 10.5, 3.13, 1 | 15 |
| PersonalizeForce::a::24 | 11.0, 4.27, 1 | 22.3, 4.15, 1 | 1 | 6.18, 3.74, 1 | 23.2, 5.49, 1 | 1 |

The id's product is on top from the raw question alone on every question in both columns.

## The three questions asked

1. **Does the passage role give the fit lists a separable top?** No list has a break in its
   top 100 (12 in the query role), the largest top-50 spacing is the tail's own (4.30 against
   4.32 for an exponential tail), and the top-1 stands 3.4 s above the bulk against 8.6; what
   the passage role has that the query role has not is an absolute identity level
   (0.975 – 0.995), reached by one or two graph tags for 30 of the 100 query tags, with a step
   of 0.025 cosine (0.45 s) down to the next tag.
2. **Does it lift the description above its noise level?** Top-1 z 3.96 against 3.75 (3.75
   against 3.85 in spreads of the upper half), the largest of 4,808 normal values 3.63; no
   chunk above the universal threshold on 7 of 10 questions against 6.
3. **Does the exact chance correction remove the tag-count dependence?** With the fits
   shuffled ρ is 0.01 and 0.005 (−0.20 with −ln n_c, 0.26 with none); with the observed fits
   0.04 and −0.07 (−0.24 to 0.12 over the questions); the same correction takes the edge
   standing out of the comparison between chunks (ρ with the chunk's best edge standing −0.04
   and −0.26, against 0.64 and 0.52 uncorrected).

## Not verified in H

- The role of the stored chunk descriptions: read in code, not measured.
- Why the local passage embedding reaches the stored tag vectors at 0.991 and not 1.000.
- F′'s chunk-level value for a tag handle is a reading; three readings are reported.
- The break detector assumes an exponential tail under no break; on Student-t(6) lists it
  reports a break on 25 of 200.
- One cached interpretation per question; one seed for the shuffles; no gold, no recall.

## Files of H

- `scratch/collect_symmetric.py` (334 s) → `scratch/symmetric_arrays.npz` (13 MB, numbers only),
  `scratch/identity_passage.json`, `scratch/collect_symmetric.out.txt`. It reads the first
  collection's `evidence_arrays.npz` (session scratchpad).
- `scratch/analyse_symmetric.py` → `scratch/results_symmetric.json`;
  `scratch/make_tables_symmetric.py`; `scratch/selftest_gaps.py`, `selftest_gaps.out.txt`;
  `scratch/crosscheck_symmetric.py`; the added estimators in `scratch/instrument_lib.py`
  (`gap_stats`, `spacing_reference`, `fisher_g_p`, `chance_corrected`).
