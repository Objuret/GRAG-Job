# Facet-Derivation Methods — Reference Survey

A literature catalog of every method found for **assigning per-facet semantic structure to an
already-built corpus of short phrase-tags (each ≤ ~12 words) plus their sentence-embeddings**,
under the constraint that **no generative LLM may create facet values at build time**.

This is a neutral reference: each method gets *what it is · citation · build-time vs query-time ·
label/LLM requirements · failure mode*. It does not recommend an architecture. Compiled
2026-06-27 from a 12-lane web/literature dig.

> **Target facets** (the v3 artefact "content profile"): `process/activity`,
> `information-kind` (definition / example / metric / argument / procedure / case_study /
> raw_data), `entity-type` (person / org / product / system / place), plus `centrality`
> (topic-as-degree — how central a tag is to its chunk vs its sibling tags).
>
> **Constraint vocabulary.** *Generative LLM* = an autoregressive decoder prompted to emit
> tokens that are parsed into a value (excluded at build time). *Discriminative encoder* =
> encoder-only model + classification head outputting a score over fixed classes, no decoding
> (a distinct middle tier — flagged per method, inclusion is a design choice). *Geometric/
> statistical* = pure embedding algebra or counting, no model judgment.

---

## 0. The three architectural paths

Every method below serves one of three ways to impose facet structure on the tag cloud:

- **Path A — Named axes (seed → project).** Define each facet as a direction/region from a
  handful of seed words/tags; project every tag onto it; the facet value is the projection.
  Build-time, geometric. (§3)
- **Path B — Emergent structure (cluster/decompose → name).** Let the cloud's own geometry
  produce a soft coordinate per tag (mixture over discovered components); align/name the
  components to the intended facets afterward. Build-time, geometric. (§4)
- **Path C — Query-time projection (no baked facets).** Store nothing per-facet; at query
  time decompose the prompt into facet-aspects, score each against the plain tag embeddings,
  fuse. The facet structure lives only in the live comparison. (§5)

Two layers cut across all three: a **geometry-preprocessing prerequisite** (§1) and a
**corpus-relative distinctiveness** layer (§6). Three facets have their own dedicated
literatures: **centrality** (§7), **information-kind** (§8), **entity-type** (§9). The
**weak-supervision / discriminative-classifier** machinery that fuses cheap signals is §10.
Cross-cutting empirical findings are §11.

---

## 1. Geometry preprocessing (prerequisite for Paths A & B)

Raw cosine over sentence embeddings is partly corrupted; measure and lightly repair before any
distance-based method. **Key tension:** isotropy and clusters are provably incompatible — full
whitening helps graded ranking but erases cluster structure.

### 1.1 The pathologies (diagnosis)
- **Representation degeneration / cone effect** — weight-tied training pushes embeddings into a
  narrow cone; unrelated items get high cosine. *Gao et al., "Representation Degeneration Problem
  in Training Natural Language Generation Models," ICLR 2019* — https://arxiv.org/pdf/1907.12009.
- **Anisotropy measured** — random same-layer pairs have cosine often > 0.5 across BERT/ELMo/GPT-2.
  *Ethayarajh, "How Contextual are Contextualized Word Representations?," EMNLP 2019* —
  https://aclanthology.org/D19-1006/.
- **Rogue dimensions** — 1–3 dims dominate cosine; per-dim z-scoring corrects them. *Timkey & van
  Schijndel, "All Bark and No Bite: Rogue Dimensions… Obscure Representational Quality," EMNLP 2021*
  — https://aclanthology.org/2021.emnlp-main.372/.
- **Hubness** — in high-d a few points are NN to disproportionately many; corrupts kNN graphs and
  clustering. *Radovanović, Nanopoulos, Ivanović, "Hubs in Space," JMLR 11, 2010* —
  https://www.jmlr.org/papers/volume11/radovanovic10a/radovanovic10a.pdf. Role in clustering:
  *Tomašev et al., "The Role of Hubness in Clustering High-Dimensional Data," PAKDD 2011*.
- **Distance concentration** — as d→∞ nearest/farthest distances converge. *Beyer et al., "When Is
  'Nearest Neighbor' Meaningful?," ICDT 1999*; converse (stays meaningful if *relevant* dims grow):
  *Durrant & Kabán, J. Complexity 2009* — https://www.sciencedirect.com/science/article/pii/S0885064X09000260.
- **Intrinsic dim ≪ nominal** — text embeddings have ID ≈ 11–37 vs nominal 1024–4096, so
  concentration is usually *not* fatal. *"Redundancy, Isotropy, and Intrinsic Dimensionality of
  Prompt-based Text Embeddings," 2025* — https://arxiv.org/html/2506.01435v1.

### 1.2 The fixes (lightest first)
- **Mean-centering** — subtract the global mean; restores near-isotropy. Corroborated in *You,
  "Semantics at an Angle…," 2025* — https://arxiv.org/pdf/2504.16318.
- **Mean-bias renormalization (R2)** — remove the component along the near-constant mean vector,
  renormalize. *"Correcting Mean Bias in Text Embeddings…," 2025* — https://arxiv.org/html/2511.11041v1.
- **All-but-the-Top** — subtract mean + project out top ~D/100 PCA directions. *Mu & Viswanath,
  "All-but-the-Top," ICLR 2018* — https://arxiv.org/pdf/1702.01417.
- **BERT-whitening** — linear: zero-mean, identity-covariance (+ dim reduction). *Su et al.,
  "Whitening Sentence Representations…," 2021* (arXiv:2103.15316); *Huang et al., "WhiteningBERT,"
  Findings EMNLP 2021* — https://arxiv.org/pdf/2104.01767.
- **BERT-flow** — invertible normalizing flow to an isotropic Gaussian (heaviest; needs training).
  *Li et al., EMNLP 2020* — https://aclanthology.org/2020.emnlp-main.733/.
- **PCA- vs ZCA-whitening** — ZCA (Mahalanobis) rotates back to stay closest to the original; prefer
  ZCA for interpretability. *Kessy, Lewin, Strimmer, "Optimal Whitening and Decorrelation," 2018* —
  https://arxiv.org/pdf/1512.00809.
- **Soft-ZCA** — shrinkage ε on eigenvalues: `W=(Σ+εI)^(-1/2)`; partial whitening beats full. *"Isotropy
  Matters: Soft-ZCA Whitening… for Semantic Code Search," ESANN 2025* —
  https://www.esann.org/sites/default/files/proceedings/2025/ES2025-58.pdf.
- **Cluster-local isotropy** — remove cluster-local dominant directions, not one global transform.
  *Rajaee & Pilehvar, ACL 2021* — https://aclanthology.org/2021.acl-short.73/; *Cai et al., "Isotropy
  in the Contextual Embedding Space," ICLR 2021*.

### 1.3 The whitening-vs-clusters trap (load-bearing caveat)
- *Rudman & Eickhoff, "Isotropy, Clusters, and Classifiers," 2024* — https://arxiv.org/html/2402.03191v2:
  a point cloud cannot be both isotropic and well-clustered; optimal isotropy maximizes intra-cluster
  distance. Corroborated: *"Whitening Not Recommended for Classification Tasks in LLMs," 2024* —
  https://arxiv.org/pdf/2407.12886. → for facet *clusters*, do not full-whiten.

### 1.4 Diagnostics & hubness fixes
- **IsoScore** — covariance-vs-identity isotropy measure (0–1). *Rudman et al., Findings ACL 2022* —
  https://aclanthology.org/2022.findings-acl.262/ (PyPI `IsoScore`).
- **Intrinsic-dim estimators** — *TwoNN* (1st/2nd-NN ratio): *Facco et al., Sci. Rep. 2017* —
  https://www.nature.com/articles/s41598-017-11873-y; *MLE*: *Levina & Bickel, NIPS 2004*.
- **Hubness reduction** — Mutual Proximity, Local Scaling, NICDM, DisSimLocal. *Schnitzer et al.,
  "Local and Global Scaling Reduce Hubs in Space," JMLR 13, 2012*; empirical comparison *Feldbauer &
  Flexer, KAIS 2019* — toolbox `scikit-hubness`.
- **Mutual-kNN graph** — edge only if mutually in each other's kNN; bounds degree, structurally kills
  hubs. Used in UMAP — https://umap-learn.readthedocs.io/en/latest/mutual_nn_umap.html.

---

## 2. Cross-path building blocks: kNN graph & ANN

- **Exact kNN / ε-graph / mutual-kNN** — substrate for graph methods (§4, §7). *Maier, Hein, von
  Luxburg, NIPS 2009* (graph choice affects clustering).
- **HNSW** — multi-layer navigable small-world ANN index. *Malkov & Yashunin, IEEE TPAMI 2016/2020* —
  https://arxiv.org/abs/1603.09320.
- **NN-Descent** — "neighbor's neighbor" local search; the standard fast big-kNN builder. *Dong,
  Charikar, Li, WWW 2011* — https://www.cs.princeton.edu/cass/papers/www11.pdf.
- **FAISS** (PQ + GPU) — billion-scale ANN. *Johnson, Douze, Jégou, 2017* — https://arxiv.org/abs/1702.08734.
- **Edge weighting** — heat/Gaussian kernel (von Luxburg tutorial 2007); self-tuning local scaling
  *Zelnik-Manor & Perona, NIPS 2004*.

---

## 3. Path A — Named axes (seed → project)

Build a named direction/region from seed words/tags; score any tag (and any query) by projection.
This is the literal "guide link": one anchor scores both sides. All build-time, geometric, no
generative LLM; need only seed words (a human act, not a model call).

- **SemAxis** — axis = mean(+pole seeds) − mean(−pole seeds); score = cosine projection. *An, Kwak,
  Ahn, ACL 2018* — https://aclanthology.org/P18-1228/ · code https://github.com/ghdi6758/SemAxis.
  Failure: seed/pole choice strongly affects axis; bipolar framing wrong for non-gradable categories.
- **Semantic projection** — same mechanics; shown to recover *graded* human feature values across many
  feature types. *Grand, Blank, Pereira, Fedorenko, Nature Human Behaviour 6, 2022* —
  https://www.nature.com/articles/s41562-022-01316-8.
- **POLAR** — reparametrize the whole space into a basis of antonym (semantic-differential) axes.
  *Mathew et al., WWW 2020* — https://dl.acm.org/doi/10.1145/3366423.3380227 · code
  https://github.com/Sandipan99/POLAR.
- **SensePOLAR** — POLAR for contextual embeddings, word-sense aware; neutral on irrelevant axes.
  *Engler et al., Findings EMNLP 2022* — https://aclanthology.org/2022.findings-emnlp.338/.
- **FrameAxis** — per-document bias + intensity over many microframe axes, with a null-model
  significance test (corpus-relative calibration). *Kwak, An, Ahn, PeerJ CS 2021* —
  https://peerj.com/articles/cs-644/.
- **Adjusting interpretable dimensions with human judgments** — regularize seed axes with a few
  ratings; *test whether a property even has a discernible axis before trusting it*. *Erk &
  Apidianaki, NAACL 2024* — https://aclanthology.org/2024.naacl-long.146/. Direct process/activity
  precedent: *Neu, Dillon, Erk, "…agentivity and telicity…," 2025*, arXiv:2511.16824.
- **Geometry of Culture** — difference-vector axes recover real cultural dimensions; proof content
  concepts are linear. *Kozlowski, Taddy, Evans, American Sociological Review 84(5), 2019* —
  https://journals.sagepub.com/doi/10.1177/0003122419877135.
- **Difference-of-means / Contrastive Activation** — direction = mean(pos) − mean(neg) over example
  vectors (examples can be whole tags). *Rimsky et al., "Steering Llama 2 via CAA," ACL 2024*,
  arXiv:2312.06681.
- **TCAV / CAV** — concept = normal of a linear classifier separating concept-present vs random.
  *Kim et al., ICML 2018* — https://proceedings.mlr.press/v80/kim18d/. (Needs labeled concept sets.)
- **Bolukbasi concept subspace** — direction via PCA of definitional contrast pairs. *Bolukbasi et al.,
  NeurIPS 2016* — https://arxiv.org/abs/1607.06520.
- **LDIR — anchor-text dimensions** — each dim = similarity to a sampled anchor text; pure geometry.
  *2025*, arXiv:2505.10354.
- **Parallax** — interactive projection onto user-defined concept axes. *ACL 2019* — https://aclanthology.org/P19-3028.
- **Dataless / label-embedding classification** — embed item + each facet *name*; assign by nearest
  cosine (the categorical analogue of an axis). *Chang, Ratinov, Roth, Srikumar, AAAI 2008* —
  https://cogcomp.seas.upenn.edu/papers/CRRS08.pdf. (Also §10.)
- *(Supervised, label-light, no LLM:)* **Concept Whitening** (trains the encoder to align axes;
  needs retraining) *Chen, Bei, Rudin, Nature Machine Intelligence 2020*, arXiv:2002.01650;
  **Concept Embedding Models / CT-CBM (text)** *Barbiero et al., 2025* arXiv:2406.14335; *De Santis
  et al., 2025* arXiv:2502.11100 (CT-CBM mints concepts with a *small* LM — borderline).

---

## 4. Path B — Emergent structure (cluster / decompose → name)

The tag cloud's own geometry yields a soft coordinate per tag; components are then aligned to the
intended facets. All build-time, geometric, no generative LLM (LLM only optional for naming, and
replaceable by seeds / c-TF-IDF / nearest-word).

### 4.1 Soft per-tag coordinate (decomposition)
- **Archetypal Analysis** — each tag = convex combination of K archetypes (hull extremes); weights =
  soft simplex coordinate; archetypes are real-ish tags (readable). *Cutler & Breiman, Technometrics
  1994*; survey arXiv:2504.12392 (2025). Variants: Archetypoid (*Epifanio 2016*), Kernel AA (*Mair
  et al. 2017*). Failure: init/outlier-sensitive (hull → garbage tags distort).
- **NMF (parts-based)** — non-negative factorization; W row = soft additive loadings. *Lee & Seung,
  Nature 401, 1999* — https://www.nature.com/articles/44565. Embeddings have negatives → use
  **Semi-/Convex-NMF** (*Ding, Li, Jordan, IEEE TPAMI 2010*) or run on a tag×term matrix.
  Seeded/anchored: *"Guided NMF," arXiv:2010.11365*; *"Constrained NMF for Guided Topic Modeling,"
  EMNLP 2025*.
- **ICA of embeddings** — rotate to independent, sparse, interpretable axes; each tag loads on a few;
  axes consistent across languages/models. *Yamagiwa, Oyama, Shimodaira, EMNLP 2023* —
  https://aclanthology.org/2023.emnlp-main.283/; ordering *Axis Tour*, arXiv:2401.06112.
- **Sparse coding / dictionary learning** — each vector = sparse combination of overcomplete atoms.
  *Olshausen & Field, Nature 1996* — https://www.nature.com/articles/381607a0; text: *Arora et al.,
  "Linear Algebraic Structure of Word Senses," TACL 2018*; **SPINE** *Subramanian et al., AAAI 2018*.
- **Sparse Autoencoders (SAE)** — overcomplete monosemantic features; sparse activation = soft
  coordinate + per-feature saliency. *Cunningham et al., "Sparse Autoencoders Find Highly
  Interpretable Features," ICLR 2024* — arXiv:2309.08600; on retrieval embeddings: *"Decoding Dense
  Embeddings," 2025* — arXiv:2506.00041; *"Interpretable Embeddings… A Data Analysis Toolkit," 2025*
  arXiv:2512.10092; *"Model Directions, Not Words," 2025* arXiv:2507.23220; *Bricken et al., "Towards
  Monosemanticity," 2023*; *Templeton et al., "Scaling Monosemanticity," 2024*. (Feature *naming*
  uses an LLM — replaceable by seeds; discovery/activations are LLM-free.)
- **SpLiCE — Sparse Linear Concept Embeddings** — NN-LASSO writes each embedding as a sparse
  non-negative combination over a concept dictionary (dictionary = seed-word embeddings); weights =
  per-facet coordinate. *Bhalla et al., NeurIPS 2024* — https://arxiv.org/abs/2402.10376.
- **Semantic Component Analysis** — embeddings → soft distribution over unit semantic components.
  *2024* — https://arxiv.org/abs/2410.21054.
- **S3E — semantic subspace sentence embedding** — cluster a sentence's word embeddings into
  subspaces. *Wang & Kuo, ICPR 2020* — https://arxiv.org/abs/2002.09620.
- **Codebook multi-sense phrase/sentence embeddings** — predict K codebook facet vectors per phrase;
  *asymmetric* similarity → a principled generality/centrality signal. *Chang, Lee, McCallum, AAAI
  2021* — https://arxiv.org/abs/2103.15330. (Caveat: on very short *phrases*, multi-facet did **not**
  beat single-vector.)
- **MFCVAE — Multi-Facet Clustering VAE** — one Mixture-of-Gaussians per facet; the same set cut into
  several independent partitions simultaneously, soft per-facet assignment, unsupervised. *Falck et
  al., NeurIPS 2021* — https://arxiv.org/abs/2106.05241.
- **Multiple/alternative & subspace clustering** — orthogonal clusterings = independent facets. *Niu,
  Dy, Jordan, IEEE TPAMI* (iterative alt. views); **MISC** arXiv:1905.04191.

### 4.2 Mixed-membership topic models (soft coordinate)
- **LDA** — document-topic distribution θ = soft coordinate; short-text-sparse for tags → biterm /
  embedding-enriched variants. *Blei, Ng, Jordan, JMLR 2003*; biterm arXiv:2003.11948.
- **CorEx / Anchored CorEx** — information-theoretic; seed/anchor words steer topics to named facets.
  *Gallagher et al., TACL 2017* — https://aclanthology.org/Q17-1037/ · code corex_topic.
- **Topic-Aspect Model (TAM)** — joint topic + orthogonal aspect dimension. *Paul & Girju, AAAI 2010*.

### 4.3 Cluster-then-name (hard / fuzzy)
- **HDBSCAN** — density clusters + soft `all_points_membership_vectors`; GLOSH outlier/typicality.
  *Campello, Moulavi, Sander, PAKDD 2013*.
- **UMAP / t-SNE / PaCMAP** — dim-reduction front-end (can manufacture/destroy structure). *McInnes,
  Healy, Melville, 2018* arXiv:1802.03426.
- **BERTopic** — embeddings → UMAP → HDBSCAN → c-TF-IDF naming; guided/seeded variant aligns to named
  facets. *Grootendorst, 2022* — https://arxiv.org/abs/2203.05794.
- **Top2Vec** — dense regions in joint doc+word space as topic vectors; nearest-word naming. *Angelov,
  2020* — https://arxiv.org/abs/2008.09470.
- **Spherical k-means** — k-means on L2-normalized embeddings (cosine). *Dhillon & Modha, Machine
  Learning 2001*.
- **GMM / fuzzy c-means** — soft membership = facet coordinate (needs dim-reduction/whitening in high-d).
- **ABAE** — autoencoder with attention; reconstructs a sentence as a combo of K aspect embeddings;
  weights = soft aspect distribution. *He, Lee, Ng, Dahlmeier, ACL 2017* — https://aclanthology.org/P17-1036/.
- **Self-enhancement unsupervised aspect category detection** — seed refinement + self-training.
  *Nguyen et al., Findings 2023* — https://arxiv.org/abs/2311.09708.

### 4.4 Graph community detection (note: yields *topics*, not orthogonal facets)
- **Louvain** — greedy modularity partition. *Blondel et al., J. Stat. Mech. 2008* — arXiv:0803.0476.
  (Can yield disconnected/badly-connected communities; resolution limit.)
- **Leiden** — guaranteed well-connected communities; CPM objective is resolution-limit-free. *Traag,
  Waltman, van Eck, Sci. Rep. 2019* — https://www.nature.com/articles/s41598-019-41695-z.
- **Label Propagation** — near-linear, unstable. *Raghavan, Albert, Kumara, 2007* — arXiv:0709.2938.
- **Infomap** — flow/MDL-based. *Rosvall & Bergstrom, PNAS 2008*.
- **Walktrap** — random-walk distance hierarchy. *Pons & Latapy, 2005*.
- **Stochastic Block Model (degree-corrected, nested)** — inferential; overlap-capable; resolution-
  limit-robust. *Karrer & Newman, 2011*; *Peixoto* (graph-tool).
- **Spectral clustering** — eigenvectors of the graph Laplacian; the eigen-embedding gives soft
  coordinates. *von Luxburg tutorial, 2007* — arXiv:0711.0189. Scale via *Nyström*.
- **Laplacian Eigenmaps** — locality-preserving soft manifold coordinates. *Belkin & Niyogi, Neural
  Computation 2003*.
- **Diffusion Maps** — coordinates = diffusion distance, multi-scale. *Coifman & Lafon, ACHA 2006*.
- **Consensus / multiresolution clustering** — stable partition across resolutions. *Lancichinetti &
  Fortunato 2012*; *Jeub et al., Sci. Rep. 2018*.
- **Caveats:** resolution limit (*Fortunato & Barthélemy, PNAS 2007*); descriptive methods find
  "communities" in random graphs → prefer inferential SBM (*Peixoto, "Descriptive vs. Inferential
  Community Detection," Cambridge Elements 2023*).
- **Tag co-occurrence network / hypergraph** — edges from tags co-occurring in a chunk (usage, not
  embedding geometry). *Cattuto et al., "Emergent Community Structure in Social Tagging Systems," 2009*
  — arXiv:0812.0698; **FolkRank** *Hotho et al., 2006*.

### 4.5 Sense/polysemy induction (background for "a tag has multiple readings")
- **Multi-prototype / sense induction** — *Reisinger & Mooney 2010*; *Neelakantan et al., 2014*
  (MSSG/NP-MSSG) arXiv:1504.06654; **AdaGram** *Bartunov et al. 2016*. **Watset** (graph sense/frame
  induction) *Ustalov et al., CL 2019* — arXiv:1808.06696.

### 4.6 Naming/aligning emergent components without an LLM
- **c-TF-IDF** cluster labeling (*Grootendorst 2022*); **nearest-word / medoid** labeling; **seed/
  anchor steering** (SemAxis poles, Anchored CorEx, Guided NMF, guided/zero-shot BERTopic);
  **X-Class** (GMM init from facet-name centroids → "we know which cluster is which class") *Wang,
  Mekala, Shang, NAACL 2021* — https://aclanthology.org/2021.naacl-main.242/; **Generalized Category
  Discovery** (match cluster centroids to labeled class centroids) *Vaze et al., CVPR 2022* —
  arXiv:2201.02609; **NPMI / word-intrusion coherence** for cut selection (with the caveat that
  automated coherence diverges from humans — *"Is Automated Topic Model Evaluation Broken?," NeurIPS
  2021*). The naming problem is acknowledged hard: *"Towards explainable community finding," Applied
  Network Science 2022*.

---

## 5. Path C — Query-time projection (no baked facets)

Index stays plain; facet structure is computed live from the prompt. The only model is the
query-time interpreter (allowed); index-side stays LLM-free.

### 5.1 Query-time aspect decomposition + per-aspect match + fusion
- **Multi-Aspect Reviewed-Item Retrieval / Aspect Fusion** — query-time aspect split → each aspect
  scored against the same plain embeddings → late fusion (mean variants). Index side: plain
  embeddings only. *2024* — https://arxiv.org/html/2408.00878v1. (Watch: aspect-popularity &
  anisotropy bias in fusion.)
- **DORIS-MAE** — complex query → aspects/sub-aspects → per-aspect coverage → normalized sum.
  *NeurIPS D&B 2023* — https://arxiv.org/abs/2310.04678.
- **RAG query decomposition** — Typed-RAG, RQ-RAG, RAG-Fusion (RRF). Query-time LLM splits, retrieve
  per sub-query, merge by reciprocal-rank fusion. e.g. arXiv:2507.00355.

### 5.2 Faceted IR — automatic facet generation
- **QDMiner** — mine query facets from frequent lists in top results (deterministic, label-free).
  *Dou, Jiang, Sun, Wen, WWW/SIGIR 2011*.
- **Kong & Allan** — Hearst-candidate facet terms + graphical-model filtering (supervised). *SIGIR
  2013* — https://dl.acm.org/doi/10.1145/2484028.2484097.
- **DeepQFM** — contrastive item encoder injected into facet mining. *Deng, Dou, Wen, IR Journal 2023*.
- **NMIR** — learn multiple query-intent vectors, each decoded to a facet. *Hashemi, Zamani, Croft,
  CIKM 2021* — https://dl.acm.org/doi/10.1145/3459637.3482445.
- **Open-domain facet extraction/generation taxonomy** — *Samarinas, Dharawat, Zamani, ICTIR 2022*;
  LLM-edit variant arXiv:2403.16345.

### 5.3 The guide-link core (project both query and tag onto a shared anchor)
- **Query aspect-based term weighting regularization** — cluster query terms into aspects, reward docs
  covering more aspects. *Fang & Zhai, ECIR 2010* — https://eecis.udel.edu/~hfang/pubs/ecir10.pdf.
- **Aspect-specific subspaces** — one embedding per aspect; per-aspect cosine. **ASPIRE** (Optimal-
  Transport facet matching, co-citation supervised) *Mysore, Cohan, Hope, NAACL 2022* —
  https://aclanthology.org/2022.naacl-main.331/; **CSFCube** (Background/Method/Result benchmark)
  *Mysore et al., 2021* arXiv:2103.12906; **Ostendorff & Blume** (specialized per-aspect embeddings)
  arXiv:2203.14541; **AspectCSE** (Wikidata-property contrastive) *Schopf et al., RANLP 2023*
  arXiv:2307.07851; **SemCSE-Multi** (per-aspect projection heads, LLM-built training) arXiv:2510.11599.
- **Multi-Aspect Dense Retrieval** — one embedding per aspect, learned fusion. *Google Research* —
  research.google/pubs/multi-aspect-dense-retrieval.
- **Latent-entity / concept-space projection (EQFE)** — project query+doc into a concept space.
  *"Concept Embedding for IR," Springer 2018*.
- **FaBle — Multi-Facet Blending** — LLM-built facet-conditional training pairs (build-time LLM →
  brushes the constraint). *ACL 2025* — https://aclanthology.org/2025.acl-long.1388.
- **UniFAR — learnable facet anchors** — the guide link in trained form, LLM-supervised. *2026*
  arXiv:2602.23766.
- **ASPECTSIM** — aspect-conditioned similarity ≈ 80% better human agreement, but GPT-4o scoring
  (excluded; cite as motivation). *2026* arXiv:2601.03435.

### 5.4 Learned sparse retrieval — query-time term/aspect weighting
- **SPLADE** — MLM head → sparse vocab vector with learned expansion + weighting; SPLADE-doc pushes
  work to indexing. *Formal, Piwowarski, Clinchant, SIGIR 2021* — arXiv:2107.05720; inference-free LSR
  arXiv:2505.01452.
- **uniCOIL / COIL** — scalar per-term weights, query-time weighting. *Gao, Dai, Callan, 2021* —
  arXiv:2106.14807.
- **DeepCT / HDCT, DeepImpact** — bake term importance deterministically at index time, weight query
  live. *Dai & Callan, 2019* arXiv:1910.10687; DeepImpact arXiv:2405.17093.

### 5.5 Late interaction / multi-vector (per-token = "facet at query time")
- **ColBERT / ColBERTv2 / PLAID / WARP** — per-token embeddings, MaxSim (each query token finds its
  best doc token); docs pre-encoded, only query encoded live. *Khattab & Zaharia, SIGIR 2020* —
  arXiv:2004.12832; v2 arXiv:2112.01488; PLAID arXiv:2205.09707; WARP arXiv:2501.17788.
- **Token-importance / pruning for ColBERT** — which tokens carry the match. arXiv:2112.06540;
  arXiv:2511.16106.
- **Multi-query retrieval** — generate several query vectors. *"Beyond Single Embeddings," 2025*
  arXiv:2511.02770.

### 5.6 Conditional / instruction-aware embeddings
- **INSTRUCTOR** — embed text *with* an instruction; the same tag yields a facet-specific vector at
  query time, no retraining, no judge. *Su et al., ACL Findings 2023* — arXiv:2212.09741.

### 5.7 Diversity / aspect-coverage scorers
- **xQuAD** (coverage+novelty over sub-queries) *Santos, Macdonald, Ounis, WWW 2010*; **PM-2**
  (proportional aspect representation) *Dang & Croft, SIGIR 2012*; **IA-Select / α-nDCG** (TREC
  diversity). Subtopic mining: *NTCIR INTENT*. Scatter/Gather clustering of results *Cutting 1992*.
- **Cross-encoder reranking** — full query×tag interaction (shortlist only); the upper bound of
  query-time facet matching. *monoBERT lineage*; jina-reranker-v3 arXiv:2509.25085.

---

## 6. Corpus-relative distinctiveness statistics (the IDF-intuition layer)

A tag's value measured against the whole tag-corpus (or a facet-slice). The whole family is one
idea — *rate-in-slice vs rate-in-whole* — at rising rigor; pick one. **Caveat:** tags are
near-unique (df≈1), so raw token/string counting degenerates → coarsen the vocabulary by
clustering tag-embeddings first, then count clusters.

- **IDF / probabilistic IDF, TF-IDF (SMART variants), BM25** — *Robertson & Zaragoza, "The
  Probabilistic Relevance Framework: BM25 and Beyond," FnTIR 2009* — https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf;
  *Manning, Raghavan, Schütze, IR-book, 2008* (sublinear tf, pivoted norm).
- **Weirdness ratio / domain specificity** — rate-in-target ÷ rate-in-reference. *Ahmad et al., 1999*;
  PACLIC 2008 — https://aclanthology.org/Y08-1025.pdf.
- **Keyness — log-likelihood (Dunning G²) & odds ratio** — *Dunning, Computational Linguistics 19(1),
  1993*; LL-vs-OR purposes *Pojanapunya & Watson Todd, CLLT 2018* —
  https://www.degruyterbrill.com/document/doi/10.1515/cllt-2015-0030/html.
- **Fightin' Words — log-odds with informative Dirichlet prior** — signed, variance-stabilized,
  robust on rare terms; prior = full tag-corpus. *Monroe, Colaresi, Quinn, Political Analysis 16(4),
  2008* — impl https://github.com/kornosk/log-odds-ratio.
- **Residual IDF / burstiness** — deviation from Poisson independence. *Church & Gale, 1995*; modern
  arXiv:2604.00672.
- **c-TF-IDF** — class-based TF-IDF (facet-group as class), length-normalized. *Grootendorst, BERTopic,
  2022* — https://maartengr.github.io/BERTopic/getting_started/ctfidf/ctfidf.html.
- **Lexical specificity (hypergeometric)** — signed −log10(prob) per term per part; robust to part size.
  *Lafon, 1980*; impl `textometry::specificities`.
- **KL-divergence / relative-entropy term scoring** — per-term contribution to D(slice‖whole).
  *Manning IR-book ch. 12*; *Kraaij & Spitters, 2003*.
- **PMI / NPMI** — token-association strength (phrase cohesion; tag-tag edges). *Bouma, GSCL 2009*.
- **Dispersion — Gries' Deviation of Proportions** — generic-everywhere vs pointed-somewhere, an axis
  orthogonal to frequency. *Gries, "Analyzing Dispersion," 2020*.
- **Resnik Information Content** — IC(c) = −log p(c) over a concept hierarchy (specificity). *Resnik,
  IJCAI 1995*; intrinsic (corpus-free) variant *Seco et al., 2004*.
- **SIF — smooth inverse frequency** — token weight a/(a+p(w)) for boilerplate down-weighting. *Arora,
  Liang, Ma, ICLR 2017*.

---

## 7. Centrality (topic-as-degree: central to its chunk vs sibling tags)

Maps onto unsupervised keyphrase/sentence salience — well-solved geometrically, no LLM.

- **Cosine-to-sibling-centroid / leave-one-out typicality** — score each tag by cosine to the mean of
  its sibling tags. (Centroid-representativeness; *Radev et al., centroid summarization, 2004*.)
- **EmbedRank / KeyBERT (+ MMR)** — cosine(candidate, document), MMR for diversity. *Bennani-Smires et
  al., CoNLL 2018* — https://arxiv.org/abs/1801.04470.
- **TextRank** — PageRank on a tag-similarity graph. *Mihalcea & Tarau, EMNLP 2004*.
- **LexRank** — eigenvector centrality on a cosine graph; degree ≈ PageRank empirically. *Erkan &
  Radev, JAIR 22, 2004* — https://arxiv.org/abs/1109.2128.
- **Degree / strength centrality** — sum of cosines to siblings; cheapest, empirically ≥ PageRank.
  *Boudin, IJCNLP 2013*.
- **Within-module degree z-score + participation coefficient** — central-to-own-community vs bridge-
  between-communities (after a partition). *Guimerà & Amaral, Nature 2005*.
- **Personalized PageRank / Random-Walk-with-Restart** — restart on a chunk's tag set → "central from
  this chunk's perspective" vs globally hub. *Tong, Faloutsos, Pan, ICDM 2006*; scalable local form
  **PageRank-Nibble / forward-push** *Andersen, Chung, Lang, FOCS 2006*. Biased TextRank arXiv:2011.01026.
- **Medoid / facility-location / submodular representativeness** — *apricot*, *submodlib* arXiv:2202.10680.
- **Density/typicality scores** — GLOSH (HDBSCAN), **LOF** (*Breunig et al., SIGMOD 2000*), **LID**
  (*Houle, SISAP 2017*), mutual-kNN degree / k-occurrence count.
- **Avoid:** raw eigenvector centrality (localization onto hubs). PositionRank / TopicRank
  (*Florescu & Caragea, ACL 2017*; *Bougouin et al., IJCNLP 2013*) and RAKE (*Rose et al., 2010*) are
  alternative keyphrase rankers.

---

## 8. Information-kind classification (definition / example / metric / argument / procedure / case_study / raw_data)

**Through-line:** every classical method keys on cues in the *surrounding clause* (connectives,
copulas, verb mood, number+unit). A bare topical phrase-tag strips them — confirmed independently by
*Cohan et al. 2019* (SSC "requires the document context"), *"On the Role of Context for Discourse
Relation Classification…," 2025* (arXiv:2510.26354), and short-text-sparsity surveys. The two values
that *self-signal on a fragment* are `metric`/`raw_data` (number+unit) and `procedure` (imperative).

### 8.1 Per-value deterministic detectors (cheapest, no LLM)
- **definition** — Hearst/copula patterns ("X is a Y", "refers to", "defined as"); **Word-Class
  Lattices** *Navigli & Velardi, ACL 2010* — https://aclanthology.org/P10-1134/; **DEFT / SemEval-2020
  Task 6 (DeftEval)** *Spala et al.* — https://aclanthology.org/2020.semeval-1.41/; distant supervision
  from Wikipedia first sentences *Espinosa-Anke et al., RANLP 2015* — https://aclanthology.org/R15-1025.pdf.
- **example** — **DiMLex / Connective-Lex** discourse-marker lexicon ("for example", "e.g.", "such as")
  — https://github.com/discourse-lab/dimlex; PDTB **Instantiation** sense (*PDTB-2 manual*; IDRR survey
  arXiv:2203.02982); exemplification detector *Wang et al., NAACL 2022* — arXiv:2205.09278.
- **metric / raw_data** — **MeasEval (SemEval-2021 Task 8)** *Harper et al.* —
  https://aclanthology.org/2021.semeval-1.38/; **quantulum3** (290+ units) —
  https://github.com/nielstron/quantulum3; spaCy QUANTITY/CARDINAL/PERCENT/MONEY NER + EntityRuler.
- **procedure** — imperative-mood detection (POS/dependency: sentence-initial base-form verb);
  **TV-AfD imperative corpus** *LREC 2020* — https://aclanthology.org/2020.lrec-1.805.pdf; recipe/
  procedural extraction arXiv:2010.10156, RecipeNLG arXiv:2005.00706.
- **argument** — claim-cue lexicon ("should", "in my opinion"); **IBM Debater** claim/evidence
  *Aharoni et al., ACL ArgMining 2014*; context-independent claim ID *Daxenberger et al., EMNLP 2017*
  — arXiv:1704.07203; **ClaimBuster** *Hassan et al., KDD 2017*; fine-grained argument units
  *Trautmann et al., AAAI 2020*; UKP persuasive essays *Stab & Gurevych, CL 2017*.
- **case_study** — evidence-type taxonomy **Study / Expert / Anecdotal** (Anecdotal = named-entity +
  past-tense narrative + date/place ≈ case_study). *Rinott et al., "Show Me Your Evidence," EMNLP
  2015* — https://aclanthology.org/D15-1050/. (No dedicated detector; partial signal only.)

### 8.2 Discourse / rhetorical-role schemes (scaffolding & label sources, not phrase classifiers)
These are position/sequence-dependent and degrade out of document context; useful as label
vocabularies.
- **Argumentative Zoning (AZ, 7-cat)** *Teufel & Moens, ACL-W 1999 / CL 2002*; **AZ-II (15-cat)**
  *Teufel, Siddharthan, Batchelor, EMNLP 2009* — https://aclanthology.org/D09-1155/.
- **CoreSC / SAPIENT (11-cat)** *Liakata et al., Bioinformatics 2012*.
- **Sequential sentence classification (B/O/M/R/C)** — PubMed 200k/20k RCT *Dernoncourt & Lee, 2017*;
  *Cohan et al., "Pretrained LMs for Sequential Sentence Classification," EMNLP-IJCNLP 2019* —
  https://aclanthology.org/D19-1383/; PIBOSO / ALTA-2012.
- **Legal rhetorical role** — *Bhattacharya et al. 2019*; *Kalamkar et al. 2022*; **LegalSeg** (BiLSTM-CRF
  beats instruction-tuned LLM) arXiv:2502.05836.
- **Move analysis (Swales CARS)** — *RAAMove, LREC 2024*; **speech/dialogue acts** — DAMSL / SWBD-DAMSL
  *Jurafsky et al. 1997*.
- **PDTB Instantiation/Restatement** + implicit discourse relation recognition (implicit = the hard case).
- **Evidence that LLMs underperform here:** *Sosa et al., "Can LLMs Follow Concept Annotation
  Guidelines?," 2023* — arXiv:2311.08704 (LLMs below supervised on CoreSC; definitions hardest); the
  cue-dependence is confirmed by *Rocha et al., "Cross-Genre Argument Mining…," 2025* — arXiv:2306.04314.

### 8.3 Fusion of the cheap detectors
- **Snorkel** labeling functions (each lexicon/pattern = one LF) + label model. *Ratner et al., VLDB-J
  2017/2019* — arXiv:1711.10160.
- **GrASP** — learn human-readable patterns over POS/NER/hypernym/lexicon attributes; works on phrases.
  *Shnarch et al., LREC 2022* — https://aclanthology.org/2022.lrec-1.655/.
- **Worked template:** numerical-claim detection in finance — Snorkel LFs → discriminative classifier,
  no generative LLM. *Shah et al., ACL Findings 2024* — https://arxiv.org/abs/2402.11728.

---

## 9. Entity-type induction (person / org / product / system / place)

**Structural fact:** a bare phrase carries no context. Methods need (a) a background corpus where the
phrase recurs in is-a contexts, (b) enough phrases per type to cluster, or (c) a pre-built lookup
resource. Phrases+embeddings give (b) and (c) free; (a) cold-starts on novel/internal names.
`system` is in **no** standard taxonomy — always a custom head-word/suffix or KB-subclass rule.

### 9.1 Lookup (deterministic, zero corpus)
- **Gazetteers** — GeoNames (places, CC-BY), USGS GNIS, US Census surnames, Wikidata-derived org/product
  lists. Failure: ambiguity ("Washington"), staleness, out-of-list = no type.
- **WordNet supersense** — every noun synset has a fixed lexicographer class (noun.person → person,
  noun.group → org, noun.location → place, noun.artifact → product/system); offline lookup on the head
  noun. *WordNet lexnames*; NLTK `synset.lexname()`. Failure: common nouns only; proper/novel names absent.
- **Probase / Microsoft Concept Graph** — web-scale isA, built for short-text conceptualization (Bayesian
  P(concept|instance)). *Wu et al., SIGMOD 2012*; *Microsoft Concept Graph, Data Intelligence 2019* —
  https://www.microsoft.com/en-us/research/project/probase/; short-text *Song et al., IJCAI 2011*.
- **WebIsA Database / WebIsALOD** — >400M isA tuples from CommonCrawl via 59 Hearst patterns (free,
  self-hostable). *Seitner et al., LREC 2016* — https://aclanthology.org/L16-1056/.
- **DBpedia Spotlight** — surface form → DBpedia resource → DBpedia class (Person/Org/Place/Software/
  Device). https://www.dbpedia.org/resources/spotlight/.
- **Wikidata P31 "instance of" distant typing** — link → P31/P279 chain → bucket; precompute a
  {surface → type} table = a gazetteer.
- **Targeted Hypernym Discovery (THD) / Linked Hypernyms** — Hearst on the first Wikipedia sentence of
  the linked entity. *Kliegr, J. Web Semantics 2014*.

### 9.2 Pattern-based hypernymy (term → type from a corpus)
- **Hearst patterns** — "Y such as X", "X and other Y". *Hearst, COLING 1992* —
  https://aclanthology.org/C92-2082/. High precision, low recall; cold-starts on rare phrases.
- **Hearst Patterns Revisited (SPMI)** — PPMI matrix of (term, Hearst-hypernym) + low-rank SVD to
  predict unseen pairs. *Roller, Kiela, Nickel, ACL 2018* — https://aclanthology.org/P18-2057/ · code
  HypernymySuite.
- **KnowItAll** — Hearst + PMI web validation, self-supervised. *Etzioni et al., AIJ 2005*.
- **SemEval-2018 Task 9 Hypernym Discovery** + best system **CRIM** (pattern+embedding hybrid).
  *Camacho-Collados et al., 2018* — https://aclanthology.org/S18-1115/.

### 9.3 Distributional hypernymy (from vectors)
- **Distributional Inclusion Hypothesis** — *Geffet & Dagan, ACL 2005*. **DIVE** *Chang et al., NAACL
  2018* — arXiv:1710.00880. **HyperVec** (hierarchy in the vector norm) *Nguyen et al., EMNLP 2017*.
  **Poincaré embeddings** (hyperbolic is-a) *Nickel & Kiela, NeurIPS 2017*.

### 9.4 Seed-based (seed words per type → typed lexicon)
- **Mutual / Meta-Bootstrapping** *Riloff & Jones, AAAI 1999*; **Basilisk** (drift-resistant) *Thelen &
  Riloff, EMNLP 2002*; **Collins & Singer** (seed + co-training NEC) *1999*; **Nadeau et al.** (seed →
  web gazetteer) *2006*.
- **Set expansion** — **SetExpan** *Shen et al., ECML-PKDD 2017*; **EgoSet** *Rong et al., WSDM 2016*;
  **CGExpan** (masked-LM cloze, no generative LLM) *Zhang et al., ACL 2020*; **Intel term-set
  expansion** (kNN around seed centroid) *Mamou et al., ACL 2018*; **ProbExpan** *Li et al., EMNLP 2022*.
- **SEType — seed-guided fine-grained typing (sci/eng)** — type names + ~5 seeds/type, masked-LM seed
  enrichment + RoBERTa-MNLI entailment; explicitly LLM-free, open-set. *2024* — arXiv:2401.13129.
- **X-NER — extremely-weak NER** — one context-free example entity per type; MLM-representation
  similarity mines spans. *Wang et al., 2023/2024* — arXiv:2311.02861.

### 9.5 Clustering / class induction (group your phrases into latent types)
- **Brown clustering** *Brown et al., CL 1992*; embedding clustering for semantic-class induction;
  **TaxoGen** (recursive spherical clustering taxonomy) *Zhang et al., KDD 2018* — arXiv:1812.09551;
  **nearest-centroid / prototype seeding** (5 seed lists → 5 centroids → argmax cosine); unsupervised
  UFET via induced word senses *2024* — Springer LNCS.

### 9.6 Fine-grained & ultra-fine entity typing (FET/UFET)
All assume `mention + sentence`; degrade to a head-word/embedding prior without context.
- **FIGER** (112 Freebase types, distant supervision) *Ling & Weld, AAAI 2012*. **Context-dependent
  OntoNotes 89-type** *Gillick et al., 2014* — arXiv:1412.1820. **AFET** (partial-label denoising)
  *Ren et al., EMNLP 2016*. **UFET** (10k free-form, 9 coarse / 121 fine; head-word distant
  supervision) *Choi et al., ACL 2018* — https://aclanthology.org/P18-1009/. **Box4Types** (box
  embeddings) *Onoe et al., ACL 2021*. **LRN** (label reasoning) *Liu et al., 2021*.
- **NLI-based (discriminative, no generative LLM):** **LITE** (premise = phrase, hypothesis "[ENTITY] is
  a [TYPE]", RoBERTa-MNLI) *Li, Yin, Roth, TACL 2022* — arXiv:2202.06167; **OntoType** (MLM-prompt +
  NLI, beats ChatGPT) *Komarlu et al., KDD 2024* — arXiv:2305.12307.
- **KB-grounding:** **ZOE** (zero-shot type-compatible grounding) *Zhou et al., EMNLP 2018* —
  https://aclanthology.org/D18-1231/; **TABi** (type-aware bi-encoder) *Findings ACL 2022*.
- **Type-vector / geometry:** **Interpretable Entity Representations** (vector of posteriors over 10k
  types, rule-editable) *Onoe & Durrett, Findings EMNLP 2020* — arXiv:2005.00147; **EnCore** (coref-
  chain contrastive) *EACL 2024*; **hyperbolic FET** *López et al., RepL4NLP 2019*.
- **Denoising distant labels** — *Onoe & Durrett, NAACL 2019*; *Zhang et al., Findings ACL 2023*.
- **NER taggers (small discriminative, no generative):** spaCy (OntoNotes 18-type), Flair (*Akbik et
  al., COLING 2018*), WNUT-2017 (has PRODUCT, tuned for novel/OOV). Caveat: sequence labelers over
  *running text* — fed a bare lowercase phrase they often emit nothing.
- **Excluded as generative:** **CASENT** (seq2seq type generation) arXiv:2311.00835; any GPT-as-typer.
- **Caveat (do not train an auditable-less classifier):** supervised hypernymy models *memorize
  prototypical hypernyms* and fail on novel phrases. *Levy et al., NAACL 2015*; *Roller, Erk, Boleda,
  EMNLP 2014*.
- **Head-word rule (free baseline):** the syntactic head of the tag is a coarse-type signal (UFET's own
  distant-supervision trick); pair with a suffix lexicon ("…AB/Inc" → org, "…platform/system" → system).

---

## 10. Weak supervision & zero-shot classification (the assembly layer + the discriminative tier)

### 10.1 The discriminative-vs-generative boundary
A *generative LLM* decodes tokens. A *discriminative encoder* (NLI cross-encoder, SBERT cosine,
GLiNER, SetFit) outputs a score over fixed classes with **no decoding** — a distinct tier whose
inclusion is a design choice. Note: BART-MNLI has a generative decoder; an **encoder-only NLI model**
(DeBERTa/RoBERTa-MNLI) sidesteps that objection entirely.

### 10.2 Zero-shot / no-training classifiers
- **NLI entailment zero-shot** — label = hypothesis, text = premise, take highest entailment. *Yin,
  Hay, Roth, EMNLP-IJCNLP 2019* — https://aclanthology.org/D19-1404/; modern checkpoint **Laurer et
  al., "Building Efficient Universal Classifiers with NLI," 2023** — arXiv:2312.17543
  (`deberta-v3-…-zeroshot`). Failure modes / template sensitivity: *Ma et al., "Issues with Entailment-
  based Zero-shot Text Classification," ACL 2021* — https://aclanthology.org/2021.acl-short.99/.
- **GLiNER** — generalist NER with runtime-defined types, encoder-only, runs on CPU. *Zaratiana et al.,
  NAACL 2024* — https://arxiv.org/abs/2311.08526.
- **SBERT label-gloss cosine** — embed phrase + label glosses, argmax cosine; robust on short input.
  *Reimers & Gurevych, EMNLP 2019* — https://aclanthology.org/D19-1410/.
- **Label-name-only (document-shaped, weak on tags):** **LOTClass** *Meng et al., EMNLP 2020*;
  **X-Class** *Wang et al., NAACL 2021*; **ConWea** *Mekala & Shang, ACL 2020*; **WeSTClass** *Meng et
  al., CIKM 2018*; **NatCat** *Chu et al., AKBC 2021*; **dataless** *Chang et al., AAAI 2008*.
- **Prototypical networks / nearest-centroid** — *Snell, Swersky, Zemel, NeurIPS 2017* — arXiv:1703.05175.

### 10.3 Few-shot
- **SetFit** — contrastive Sentence-Transformer fine-tune on ~8–16 examples/class + logistic head;
  short-phrase-native; zero-shot variant via templated dataset. *Tunstall et al., 2022* — arXiv:2209.11055.
- **Karamanolakis et al.** — few-keyword teacher → embedding student. *EMNLP 2019* — arXiv:1909.00415.
- **Verbalizer-NN / NPPrompt / MaVEN** — expand seed label-words by k-NN to harden prototypes.

### 10.4 Frameworks that fuse labeling functions
- **Snorkel** (data programming) *Ratner et al., VLDB 2017/2019* — arXiv:1711.10160; theory *NeurIPS
  2016* arXiv:1605.07723. **MeTaL** (multi-task) *2018* arXiv:1810.02840. **FlyingSquid** (closed-form
  triplet) *Fu et al., ICML 2020* arXiv:2002.11955. **skweak** (NLP/NER LFs) *Lison et al., ACL 2021*
  — https://aclanthology.org/2021.acl-demo.40/; **GLaRA** (graph rule augmentation) arXiv:2104.06230.
  **WRENCH** benchmark *Zhang et al., NeurIPS 2021* — arXiv:2109.11377.
  > Terminology landmine: Snorkel's *generative label model* is a small graphical model over LF votes —
  > **not** a generative LLM.
- **Critiques:** *Zhu et al., "Weaker Than You Think," ACL 2023* (gains depend on a clean validation
  set; ~5 clean labels/class may beat the pipeline) — arXiv:2305.17442; *"Stronger Than You Think /
  BoxWRENCH," NeurIPS 2024* — arXiv:2501.07727. WRENCH finding: Majority Vote is often as good as fancy
  label models. Distant supervision root: *Mintz et al., ACL 2009*.

---

## 11. Cross-cutting empirical findings (stated neutrally)

1. **Content survives cosine; polarity/stance does not.** Antonyms share contexts → high cosine, so
   sentiment/negation is not recoverable by a single cosine axis, while topical/content within-class
   similarity reliably exceeds cross-class. (Sentiment-embedding literature; *"Testing the assumptions
   about the geometry of sentence embedding spaces," 2025* arXiv:2509.01606.) → content facets are
   geometrically tractable; postures are not.
2. **For *named* concepts, difference-of-means / seed-axis ≥ sparse autoencoders.** SAEs add no
   predictive power over a difference-of-means probe on known concepts; SAEs are for *discovering*
   unknown ones. *Kantamneni et al., 2025* arXiv:2502.16681; *Sun et al., "Use SAEs to Discover Unknown
   Concepts, Not to Act on Known Concepts," 2025* arXiv:2506.23845; *SAEBench* arXiv:2503.09532.
3. **Short phrase-tags strip clause cues.** Info-kind and entity-type methods that rely on connectives/
   copulas/verb-mood/mention-context degrade on bare tags; only number+unit (metric), imperative
   (procedure), and lookup (entity-type) self-signal. (Cohan 2019; arXiv:2510.26354; short-text surveys.)
4. **Isotropy and clusters are incompatible.** Full whitening helps graded ranking but erases facet
   clusters. *Rudman & Eickhoff, 2024* arXiv:2402.03191; arXiv:2407.12886.
5. **A single clustering yields topics, not facets.** Faceted classification = orthogonal independent
   dimensions; one partition = one clustering, and it comes out unnamed. Facets require alternative/
   subspace clustering or axis projection. (Faceted-classification refs; §4.4 caveats.)
6. **The empirical gap.** No benchmark evaluates any of this on *short context-free phrase-tags* into a
   small facet set; the cited results are on words/sentences/documents. The behavior on a real tag
   corpus is an experiment, not a literature fact.

### Umbrella surveys
- *Wehrli, Opitz et al., "Interpretable Text Embeddings and Text Similarity Explanation: A Survey,"
  EMNLP 2025* — arXiv:2502.14862.
- *Ghojogh et al., "Laplacian-Based Dimensionality Reduction… Tutorial and Survey," 2021* — arXiv:2106.02154.
- *"A Survey on Programmatic Weak Supervision,"* arXiv:2202.05433; curated list
  https://github.com/JieyuZ2/Awesome-Weak-Supervision.

---

## 12. Per-facet quick map (which sections apply)

| Facet | Build-time geometric (Path A/B) | Lookup / classifier | Query-time (Path C) | Phrase-robust? |
|---|---|---|---|---|
| `centrality` | §7 (cosine-to-centroid, TextRank, within-module-z, PPR) | — | — | yes |
| `process/activity` | §3 SemAxis (action↔state poles); §4 ICA/NMF/archetypes | — | §5 INSTRUCTOR | mostly |
| `information-kind` | §3 seed axes (weak); §4 emergent | §8 detectors + §10 Snorkel/NLI | §5 aspect fusion | metric/procedure yes; rest cue-dependent |
| `entity-type` | §3 seed-centroid; §4 clustering | §9 lookup + LITE/GLiNER | §5 INSTRUCTOR | lookup yes; novel names cold-start |

> **Note on uncertain citations.** Some primary PDFs were unreachable during the dig; a few exact
> figures were taken from abstracts/secondary sources (e.g. the FIGER 112-type list — paper cert
> expired; the verbatim UFET 9 coarse types — read from the released `ufet` type files; Hearst-SVD AP
> tables; SEType F1). Verify those specific numbers in-paper before quoting.
