---
name: retag-facet-analysis
description: "How the v1 tagger's facet design directly causes the ~18% junk tag vocab, and what v2 retag changes"
metadata: 
  node_type: memory
  type: project
  originSessionId: 394998a2-4808-4743-afe8-a2540eea4232
---

**The v1 tag pollution is a designed output of two facets, not random noise.**

## v1 tagger design ([backend/tagging/pipeline.py](../../../../../exjobbet/repo/backend/tagging/pipeline.py))
- 5 facets (pipeline.py:52, VERIFIED): `topic`, `entities`, `activity`, `temporal`, `evidence`. Each a per-chunk LLM lens.
- `w_chunk = strength × coverage_bonus` (pipeline.py:69-85): strength = sqrt(mean of squared facet strengths); coverage_bonus = (concentration)^COVERAGE_ALPHA, ALPHA=0.25. MULTI_FACET_THRESHOLD=0.50.
- separate `score` stage = `relevance_to_file`. Anthropic SDK (claude-haiku-4-5), temp 0.

## Causal link to the tag situation
- ~18% of 24,804 tags are junk: `eid_*` + years/dates. eid alone ≈16k HAS_TAG edges.
- **temporal facet** → manufactures `2024`, `2024_04_27` date tags.
- **entities facet** → model reads `eid_81582c30` in flattened prose, emits it as an entity tag. ~15k eid edges were LLM-emitted during extract (not just the regex supplement).
- **evidence facet** → produces identifier-ish tags too (pilot showed `https_github_com_postgres_postgres_pull_380`-style URL/PR tags).
- Root: chunker flattened IDs/dates/links into prose → tagger told to tag entities + time + evidence → it obliged. The three polluting facets (entities, temporal, evidence) are exactly the FACTS v2 promotes to STRUCTURE.

## CRUCIAL correction (user, 2026-05-30): facets are semantic dimensions, not extractors

The facets were NEVER meant to be keyword/identifier extractors. They are rich **semantic, relational dimensions** that were degraded in implementation into "extract the obvious tokens." Examples of intended meaning:
- `temporal` was never `2024_04_27`. It is the **time-relationship** of the content/question: retrospective vs now vs forward-looking (then/now/later), spans, ongoing concern, deadline/urgency — the topic's relevance across time.
- All five were meant to be this deep; v1 collapsed each into shallow token-spitting.

So the earlier "temporal/entities/evidence dissolve into structure" was WRONG. Correct framing:
- **Structure takes the literal FACT** — the date `2026-04-27`, the `eid_`, the PR link → hard fields + entity edges.
- **The facet keeps its intended MEANING** — the temporality (forward/back/now/span/urgency), the role/relationship of an entity, the evidentiary character of evidence. The semantic stance coexists with the structural fact; it does NOT get replaced or dropped.
- v1 conflated the two and let the facet degrade into emitting the fact. v2 separates: fact→structure, semantic stance→facet (restored to depth). Neither does the other's job.

## What v2 retag changes
1. Facts become structure BEFORE tagging: timestamps→hard fields; userId/team/author/participants→`:Employee` edges; customers→`:Customer`; PR/URL links→entities. The tagger STOPS emitting these as tags.
2. **All five facets are RESTORED to their intended semantic depth** (not dropped). The facet expresses the relational/semantic dimension; structure holds the literal fact.
3. Prompt forbids ID/date/link-shaped tokens as tags (belt-and-suspenders once facts live in structure) AND must re-specify each facet's true semantic intent.
4. Tag set + retrieval surface change → v1 RAGAS/gold-100 numbers are the polluted-graph CONTRAST baseline, not the v2 result.

OPEN: write the actual intended semantic definition of each of the five facets (topic, entities, activity, temporal, evidence) — they were never properly specified, which is why they degraded.

Open: exact v2 facet set (drop temporal entirely? keep a reduced entity facet?), and whether w_chunk coverage_bonus survives with fewer facets. Ties to [[five-open-decisions]] (weights) and the chain-bake in [[graph-is-references-not-copies]]/[[v2-build-pipeline]].

## Related
- [[v2-build-pipeline]] — re-tag decision + clean structure
- [[design-hard-fields-before-tagging]] — facts as hard fields, the rule this implements
- [[nvidia-llm-host]] — v2 tagger host (deepseek-v4-pro) the retag runs on
- [[herb-eval-is-the-artefact]] — eval oracle quarantine
