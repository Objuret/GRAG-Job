# CLAUDE.md

Only two kinds of text are facts here: his own sentences, quoted with their date, and what a
command prints. What an arm does is read from its file; what the graph holds is read by
querying it. Any other sentence, this file included, is a claim until checked.

## Where

- `prod/` — the finished system: `harness/`, `eval/`, `arms/` (lucene, vector, hybrid), `run.py`,
  `tests/`. `test/` — the artefact in progress: `arms/` (every artefact arm), `artefact/` (the
  rebuild), `graph/` (db, builders, facet tools), `tests/`. `python prod/run.py --arm <arm> --set <set>`
  from the repo root loads arms from both. Runs and their manifests in `output/`; data in `data/`.
- `docs/ENVIRONMENT.md` — the machines. `docs/canon/raw/user_turns_all.jsonl` — his typed
  messages since 2026-05-14 (`tools/canon_extract.py`); archive, nothing reads it.
- `graphify-out/` — the navigation graph over `prod/` and `test/`. Query it before grepping:
  `python -m graphify query "<question>"`, `python -m graphify explain "<node>"`,
  `python -m graphify path "A" "B"`. Rebuild with `python refresh_graph.py` (seconds, AST only),
  never `graphify --update`.
- `.claude/agents/` — the specialists, run in the background.

## Current state — print, never type

- Arms: `ls prod/arms test/arms`. Database an arm used: its run manifest.
- Graph: `MATCH (n) UNWIND labels(n) AS l RETURN l, count(*)` ·
  `MATCH (a)-[r]->(b) RETURN labels(a)[0], type(r), labels(b)[0], count(*)` · `keys()` per label.
- Facet layer on `HAS_TAG`: hash against `output/facet_weight_backup/` with
  `test/graph/backup_facet_weights.py`, `NEO4J_DATABASE` naming the graph.

## His rules, his words

- *"you should not have the questions/gold available to you, there is 0% good that can come out of taht"* (2026-08-02)
- *"just the fucking stats, YOU DONTY INTERPRET THE RESULTS"* (2026-08-05)
- *"there is no "baseline" artefact, a comparable baseline are the vector and lucene arms, no?"* · *"Report both, decide nothing"* (2026-08-05)
- *"the db only exists for the artefact and is created with it"* (2026-08-27)
- *"the tags have facetweights on the edge to the chunk saying how relevant they are according to that facet, and the facetweights from the QUERY, determines how many fucks the retrieval take to each tag's facets"* (2026-08-31)
- *"the wohle point of the facets, weights and all weights of the tags-chunks-files-query, are about "how strong/relevant is the connection for this specific query""* (2026-09-02)
- *"the chunk descriptions and the tags are supposed to work TOGETHER to find gold.. it's a combo.."* (2026-08-11)
- *"i do NOT like arbitrary choices for k or any number or value, fucking BASE it on something"* (2026-07-15)
- Nothing built, run, or written to the database without his words naming it; a "yeah" is not a go (2026-09-03).
- No agent writes a sentence about the system for a later reader (2026-09-04).

## Focus — 2026-09-05

- **The artefact finds the region and nothing orders inside it.** The nearest tags reach
  the gold inside ~150 on-product chunks (0.39 delivered, 0.95 reachable by a correct
  ordering of the same candidates). Ordering inside the region is the work, on his chain
  query → tag → chunk → file, every link *"how strong/relevant is the connection for this
  specific query"*.
- **The design on the table, his:** the v1 tagger's per-edge *choice* of facets (which
  facets it named on each tag→chunk edge; backup `output/facet_weight_backup/
  herb-eval-volmax__pilot_full_herb`, sha 109d27…) goes back on the edges as the structure.
  Magnitudes come from the graph's own counts, never a model number: how rare that facet is
  among the tag's edges, what share of the chunk's tags carry it; topic from the tag→description
  cosine. The query gets one facet profile for the whole question: the interpreter judges which
  facets and in what order, the math turns that into weights. An edge's value for a query is
  that profile dotted with what the tag is to that chunk, so the same tag ranks its chunks
  differently per query.
- **First step before any build:** one measurement inside the region, whether any entity-side
  or facet-choice quantity orders gold above non-gold there. results-analyst measures;
  designers stay gold-blind.
- **The graph `herb-eval-volmax`** carries the derived facet layer (sha 50cfd6…) since the
  09-04 revert. The 09-03 pair-record layer is backed up beside it. Its entity layer
  (Chunk→Product/Kind/Channel, Employee→Channel/Product/Org/Role/manages, Customer→Company,
  File→everything) is read by artefact_v2 as stated-scope gates and concentration regions only.
  `Chunk.created_at` is the build time, not a corpus date; `Chunk.years` is the only date.
- **Open, his to rule:** product scope as hard cut or soft evidence; what the activity facet
  is on a graph with no relation for it; which facet layer the graph carries; whether
  `artefact_v1` / `artefact_v1_det` retire with the v1 graph.
- **The repo, 09-05:** cut to code, his words and the machine recipes. `prod/` holds the
  two baselines and the harness; there is no finished artefact, every artefact arm is in
  `test/`.

## Update

An arm, database, facet layer, rule, or focus change changes this file in the same commit. At
commit: `python refresh_graph.py`, then `python tools/canon_extract.py`.
