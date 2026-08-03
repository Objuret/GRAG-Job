---
name: v2-graph-spine
description: "DECIDED 2026-06-12: the v2 graph is Source→File→Chunk→Tag only; node/attribute rule; no entity/record/branch/label nodes; hard fields = chunk attributes; chunk→file weight dead; no embedded value vocab; multi-hit = boosts only"
metadata: 
  node_type: memory
  type: project
  originSessionId: 6fefcfbd-18e6-431c-9c67-cfb7fde65736
---

**The v2 graph spine (user-decided 2026-06-12): `Source → File → Chunk → Tag`. Nothing else is a node.** This supersedes the 2026-05-30 drafted graph model (entity nodes per record, :Employee/:Customer/:PrAuthor nodes, :COVERS edges) in [[v2-build-pipeline]].

**The node/attribute rule (the lens every candidate runs through):** a thing is a **node** only when others depend on its facts to resolve themselves or retrieval walks *through* it; it is an **attribute** when it's a value you filter/boost by. Born from the user's "either they are nodes, but then we get edges to EVERY fucking chunk, or they are just attributes."

What the rule decided:
- **File = node.** It is the resolution catalog (path on disk, sha256, format, probe shape tree) every reference depends on; the hash must have ONE authoritative copy. Containment edges Source→File→Chunk stay.
- **Chunk = the finest node.** Hard-field values ride as indexed chunk attributes: author ids, time range, kind, branch/channel labels, materialized path. (Confirms [[design-hard-fields-before-tagging]] — chunk props were always the user's design.)
- **Record nodes = CUT.** "Most of them will be a chunk — two almost-same nodes" (user). Records stay addressable via references (json_pointer); no per-record nodes, no :COVERS edges.
- **Branch/collection positions = attributes** (kind, labels, path prefix), not nodes. The tree lives in the path attribute; "everything under slack" = prefix filter, not a hop.
- **Entity/metadata nodes (Employee, Customer, org hierarchy) = CUT.** The hierarchy lives in the raw metadata files, read through references at query time; ids in chunk attributes are the connection. Graph must NOT mirror the directories ("metadata islands" was assistant inertia, user killed it).
- **Chunk→file relevance weight = DEAD.** The containment edge carries no number. Its v1 job (demote filler) is solved by coherence-episode chunking; "typicality" actively hurts (buries the rare relevant aside). File-flooding of results, if eval shows it, is handled by path-prefix grouping.
- **Tag nodes are per-chunk emissions, NOT shared vocabulary (user-decided 2026-06-13).** Each emitted tag = its own node bound to exactly one chunk; same text may recur as other nodes. Nothing walks through a tag (kNN hit → its one chunk); "same phrase elsewhere" = indexed text equality. Kills the v1 residue channel (shared tags minted from oracle chunks survived the herb-eval filter) and orphan-tag bookkeeping; shared-vocab view derivable later by group-by-text (lossless direction). Embed cache keys on normalized text, so cost unchanged.
- **The pipeline embeds exactly ONE thing: phrase tags.** No field values, no descriptions, no raw chunks. A name's semantic reach already lives in the contextual phrases that mention it ("rate limiting criticized during the PitchForce migration") — better vectors than a bare value; bare-value embeddings are weak coordinates, conflate the HERB twin products, and do nothing for person names.
- **Prompt-literal matching (decided 2026-06-12, the full shape):** exact lookup + case/spacing normalization in a deterministic pre-pass → the interpreter (NO corpus vocabularies in its context — [[ai-cost-boundary]]; only tiny universal enums like kinds/answer-shapes in its fixed contract) flags from language alone what a token looks like (product-ish/person-ish) and whether it's **wanted vs EXCLUDED** ("apart from PitchForce…" — excluded = no boost, never removal; build with the interpreter, not now) → on a flagged miss, **scoped string-distance lookup against that one directory only**, read from raw via references → described-not-named things ("the pitch tool") fall to the semantic layer, no structural boost; measurable, revisit on eval evidence only.
- **Ambiguity = all candidates, confidence sets boost size.** Two Annas → both boosted; exact-unique strongest, exact-ambiguous split, distance/interpreter-resolved weaker. Jump only on exact-unique single anchor.
- **Multiple hard-field hits in one prompt = boosts only (decided).** Each hit boosts; the combination wins by addition; no multi-anchor jump machinery. Single-anchor jump (subtree-first, loud widen) survives unchanged.
- **HERB evidence (verified 2026-06-12, all 1,514 eval questions):** perfectly spelled, template-generated, products named exactly, people referenced by role never name — AND the product list holds deliberate near-twins (ContentForce/ContextForce, CollaborateForce/CollaborationForce, SearchFlow/SearchForce). So the exact layer is load-bearing (pure semantics conflates twins) and blanket typo-fuzzy is actively dangerous; typo tolerance exists ONLY as the scoped flagged-miss lookup above.
- **Closed facet labels = chunk attributes (decided 2026-06-12).** The minted hub-node-per-label idea is dead under the same rule; `function: decision` is an indexed attribute, and mapping prompt language onto labels is interpreter territory.
- **Field-handling rule (yes-in-principle, "ish"):** what happens to a field follows the shape of its values — dates → chunk time-range; ids → id-set attributes; few-distinct-values fields → label attributes; free-form names/titles → never copied, stay in raw behind references; long text → the content itself. Concrete table FINALIZED 2026-06-12 — see [[v2-mapping-key]]; the key adds only what shape can't know.

Related: [[v2-build-pipeline]] (superseded graph model), [[retriever-routing-model]], [[v2-chunking-model]], [[graph-is-references-not-copies]].
