import neo4j from 'neo4j-driver';
import type { FacetDimension } from '../types';
import type { Neo4jConfig } from './neo4j';
import type { HardGate, QueryPlan, QueryTag } from './interpreter';
import { intVal, withSession } from './neo4j';
import { embedPromptTags } from './embeddings';

const TAG_VECTOR_INDEX = 'tag_embedding';
const CHUNK_FULLTEXT_INDEX = 'chunk_fulltext';

type Session = Parameters<Parameters<typeof withSession>[1]>[0];

/**
 * Build the deterministic hard-gate WHERE fragment + params from the plan's
 * structured constraints. Materialized by `python -m tagging materialize`.
 * The fragment is ANDed onto `c` (the :Chunk) and runs BEFORE any tag or
 * embedding work. Empty when no constraint is set.
 */
function buildGate(gate: HardGate): { clause: string; params: Record<string, unknown>; active: boolean } {
  const parts: string[] = [];
  const params: Record<string, unknown> = {};
  for (const f of ['product', 'section', 'channel', 'employee_id'] as const) {
    const v = gate[f];
    if (v) { parts.push(`AND c.${f} = $g_${f}`); params[`g_${f}`] = v; }
  }
  if (gate.years.length) {
    params.g_years = gate.years.map(y => neo4j.int(y));
    parts.push('AND any(y IN $g_years WHERE y IN c.years)');
  }
  return { clause: parts.join('\n  '), params, active: parts.length > 0 };
}

/**
 * Validate every set gate value against the live corpus. A constraint that
 * matches zero chunks is a hard error, not a silent "scan everything"
 * fallback — the user asked for something the corpus does not contain and
 * must be told, with the valid values where the set is enumerable.
 */
async function validateGate(session: Session, gate: HardGate, datasetId: string | null): Promise<void> {
  const ds = '($datasetId IS NULL OR f.dataset_id = $datasetId)';
  for (const f of ['product', 'section', 'channel', 'employee_id'] as const) {
    const v = gate[f];
    if (!v) continue;
    const res = await session.run(
      `MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE ${ds} AND c.${f} = $v RETURN count(c) AS n`,
      { v, datasetId },
    );
    if ((intVal(res.records[0]?.get('n')) ?? 0) === 0) {
      const enumRes = await session.run(
        `MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE ${ds} AND c.${f} IS NOT NULL
         RETURN DISTINCT c.${f} AS v ORDER BY v LIMIT 60`,
        { datasetId },
      );
      const valid = enumRes.records.map(r => r.get('v') as string);
      throw new Error(
        `Hard-gate filter ${f}="${v}" matches no chunks in the corpus. ` +
        `Valid ${f} values: ${valid.length ? valid.join(', ') : '(none materialized — run \`python -m tagging materialize\`)'}.`,
      );
    }
  }
  if (gate.years.length) {
    const res = await session.run(
      `MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
       WHERE ${ds} AND any(y IN $ys WHERE y IN c.years) RETURN count(c) AS n`,
      { ys: gate.years.map(y => neo4j.int(y)), datasetId },
    );
    if ((intVal(res.records[0]?.get('n')) ?? 0) === 0) {
      const rng = await session.run(
        `MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk) WHERE ${ds} AND c.years IS NOT NULL
         UNWIND c.years AS y RETURN min(y) AS lo, max(y) AS hi`,
        { datasetId },
      );
      const lo = intVal(rng.records[0]?.get('lo'));
      const hi = intVal(rng.records[0]?.get('hi'));
      throw new Error(
        `Hard-gate years=[${gate.years.join(', ')}] match no chunk text in the corpus` +
        (lo != null ? ` (corpus year range ${lo}–${hi}).` : '.'),
      );
    }
  }
}

/** One prompt tag → the corpus :Tag names it grounded to, with cosine sim. */
export interface GroundedTag {
  promptTag: string;
  matches: { name: string; sim: number }[];
}

export interface RetrievedChunk {
  chunkId: string;
  fileId: string;
  content: string;
  description: string | null;
  relevanceToFile: number | null;
  score: number;
}

const DONE_GRAPH_RUN_ID = 'pilot_full_herb';
const ALL_FACETS: FacetDimension[] = ['topic', 'entities', 'activity', 'temporal', 'evidence'];

export interface RetrievalOptions {
  activeFacets?: FacetDimension[];
  tagsEnabled?: boolean;
  minWChunk?: number;
  minRelevanceToFile?: number;
  limit?: number;
  datasetId?: string | null;
  strategy?: string;
  /** Tag-grounding knobs (the interpreter "effort" control). */
  groundingK?: number;      // nearest corpus tags per prompt tag (default 10)
  minSim?: number;          // drop matches below this cosine sim (default 0.78)
  /**
   * Chunk sections to drop from retrieval (eval only). Default none — the app
   * never sets this. The RAGAS reference run excludes the QA sections so the
   * pipeline must answer from real evidence, not the gold-answer record.
   */
  excludeSections?: string[];
}

// Weighted overlap, with the grounding similarity folded in:
// score = Σ qt.w_query * qt.facets[edge.facet] * edge.w_chunk * edge.w_facet
//           * coalesce(chunk.relevance_to_file, 1) * qt.sim
// Query tags are always grounded corpus :Tag names (qt.name) with a real
// cosine sim. There is no exact-name path.
const scoreCypher = (gate: string) => `
UNWIND $queryTags AS qt
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[r:HAS_TAG]->(t:Tag {name: qt.name})
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND r.facet IN $activeFacets
  AND coalesce(r.w_chunk, 0.0) >= $minWChunk
  AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
  ${gate}
WITH c, r, qt,
     CASE r.facet
       WHEN 'topic'    THEN qt.topic
       WHEN 'entities' THEN qt.entities
       WHEN 'activity' THEN qt.activity
       WHEN 'temporal' THEN qt.temporal
       WHEN 'evidence' THEN qt.evidence
       ELSE 0.0
     END AS facetScore
WITH c,
     sum(qt.w_query * facetScore * r.w_chunk * r.w_facet
         * coalesce(c.relevance_to_file, 1.0)
         * qt.sim) AS score
WHERE score > 0
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       round(score, 4) AS score
ORDER BY score DESC
LIMIT $limit
`;

const baselineCypher = (gate: string) => `
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND c.relevance_to_file IS NOT NULL
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  ${gate}
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       c.relevance_to_file AS score
ORDER BY c.relevance_to_file DESC
LIMIT $limit
`;

// Lexical recall over the actual extracted text via the chunk_fulltext index,
// hard-gated by the same structured constraints. This is the literal-search
// path: the chunk is reachable by a term in its body even if no matching tag
// was ever minted (the original gap). Score = normalized Lucene score.
const lexicalCypher = (gate: string) => `
CALL db.index.fulltext.queryNodes($idx, $q) YIELD node AS c, score AS lex
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  ${gate}
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       round(lex, 4) AS score
ORDER BY lex DESC
LIMIT $limit
`;

function rowToChunk(rec: Record<string, unknown>): RetrievedChunk {
  return {
    chunkId: rec.chunkId as string,
    fileId: rec.fileId as string,
    content: rec.content as string,
    description: (rec.description ?? null) as string | null,
    relevanceToFile: intVal(rec.relevanceToFile),
    score: (intVal(rec.score) ?? 0),
  };
}

interface ScoreTagParam {
  name: string;          // grounded corpus :Tag name
  sim: number;           // grounding cosine similarity
  w_query: number;
  topic: number; entities: number; activity: number; temporal: number; evidence: number;
}

function facetCols(qt: QueryTag) {
  return {
    w_query: qt.w_query,
    topic: qt.facets.topic,
    entities: qt.facets.entities,
    activity: qt.facets.activity,
    temporal: qt.facets.temporal,
    evidence: qt.facets.evidence,
  };
}

/**
 * Grounding: embed each prompt tag (e5 `passage:`, symmetric with the corpus
 * side — see embeddings.ts) and kNN against the
 * `tag_embedding` index to expand it onto real corpus :Tag names. Each
 * grounded name inherits the prompt tag's facet vector + w_query and carries
 * the cosine sim, which the scorer folds into the weight.
 */
async function groundQueryTags(
  plan: QueryPlan,
  session: Parameters<Parameters<typeof withSession>[1]>[0],
  k: number,
  minSim: number,
): Promise<{ params: ScoreTagParam[]; grounding: GroundedTag[] }> {
  const vectors = await embedPromptTags(plan.tags.map(t => t.t), plan.description);
  const params: ScoreTagParam[] = [];
  const grounding: GroundedTag[] = [];

  for (let i = 0; i < plan.tags.length; i++) {
    const qt = plan.tags[i];
    const vec = vectors[i];
    if (!vec) continue;
    const res = await session.run(
      `CALL db.index.vector.queryNodes($idx, $k, $vec) YIELD node, score
       RETURN node.name AS name, score AS sim`,
      { idx: TAG_VECTOR_INDEX, k: neo4j.int(Math.max(1, k)), vec },
    );
    const matches: { name: string; sim: number }[] = [];
    for (const rec of res.records) {
      const name = rec.get('name') as string;
      const sim = Number(rec.get('sim'));
      if (!name || !Number.isFinite(sim) || sim < minSim) continue;
      matches.push({ name, sim: Math.round(sim * 1e4) / 1e4 });
      params.push({ name, sim, ...facetCols(qt) });
    }
    grounding.push({ promptTag: qt.t, matches });
  }
  return { params, grounding };
}

function retrievalLimit(plan: QueryPlan, options?: RetrievalOptions): number {
  const raw = Number(options?.limit ?? plan.filters.limit ?? 20);
  return Math.max(1, Math.min(500, Number.isFinite(raw) ? raw : 20));
}

function retrievalDataset(plan: QueryPlan, options?: RetrievalOptions): string | null {
  return options?.datasetId ?? plan.filters.dataset_id ?? null;
}

function activeFacets(options?: RetrievalOptions): FacetDimension[] {
  if (!options?.activeFacets) return ALL_FACETS;
  return options.activeFacets.filter((f): f is FacetDimension => ALL_FACETS.includes(f as FacetDimension));
}

const EMPTY_GATE: HardGate = {
  product: null, section: null, channel: null, employee_id: null, years: [],
};

function gateOf(plan: QueryPlan): HardGate {
  return plan.filters?.gate ?? EMPTY_GATE;
}

function rowsToChunks(records: { keys: PropertyKey[]; get: (k: string) => unknown }[]): RetrievedChunk[] {
  return records.map(rec => {
    const obj: Record<string, unknown> = {};
    for (const key of rec.keys) obj[key as string] = rec.get(key as string);
    return rowToChunk(obj);
  });
}

// Lucene query for the gated lexical path: the prompt's own tags plus any
// explicit year literals. Special chars are stripped so user text can't break
// the parser. Years are the key term for temporal/literal queries.
function buildLexQuery(plan: QueryPlan): string {
  const terms = [
    ...plan.tags.map(t => t.t),
    ...gateOf(plan).years.map(String),
  ]
    .map(s => s.replace(/[+\-&|!(){}[\]^"~*?:\\/]/g, ' ').trim())
    .filter(Boolean);
  return [...new Set(terms)].join(' ') || plan.description.replace(/[+\-&|!(){}[\]^"~*?:\\/]/g, ' ').trim();
}

async function runLexical(
  session: Session, plan: QueryPlan, gateClause: string, gateParams: Record<string, unknown>,
  limit: number, datasetId: string | null,
): Promise<RetrievedChunk[]> {
  const q = buildLexQuery(plan);
  if (!q) return [];
  const res = await session.run(lexicalCypher(gateClause), {
    idx: CHUNK_FULLTEXT_INDEX, q, limit: neo4j.int(limit), datasetId, ...gateParams,
  });
  return rowsToChunks(res.records);
}

export async function retrieveChunks(plan: QueryPlan, cfg: Neo4jConfig, options: RetrievalOptions = {}): Promise<RetrievedChunk[]> {
  const limit = retrievalLimit(plan, options);
  const datasetId = retrievalDataset(plan, options);
  const facets = activeFacets(options);
  const gate = gateOf(plan);
  const { clause, params: gateParams, active: gated } = buildGate(gate);

  // Eval-only: AND a section-exclusion onto the same `c` predicate block, so
  // the QA gold-answer record can't be retrieved into its own evaluation.
  // Empty by default → byte-identical to the app path.
  const exSecs = (options.excludeSections ?? []).filter(Boolean);
  const exFrag = exSecs.length ? "AND NOT coalesce(c.section, '') IN $excludeSections" : '';
  const clauseX = [clause, exFrag].filter(Boolean).join('\n  ');
  const paramsX = exSecs.length ? { ...gateParams, excludeSections: exSecs } : gateParams;

  return withSession(cfg, async (session) => {
    // Hard gate is validated up-front: an unknown constraint value is a loud
    // error, never a silent "ignore it and scan everything".
    if (gated) await validateGate(session, gate, datasetId);

    if (options.strategy === 'relevance' || options.tagsEnabled === false) {
      return retrieveBaseline(limit, cfg, datasetId, gate);
    }

    const haveTags = plan.tags.length > 0 && facets.length > 0;

    // No usable tags but a hard constraint exists → the structured query is
    // still answerable via the gated lexical path. This is the intended
    // structured route, not a degradation; surface it as a warning so it is
    // never silent.
    if (!haveTags) {
      if (!gated) return [];
      plan.warnings.push('No tags from prompt — answered via the hard-gate + full-text path only.');
      return runLexical(session, plan, clauseX, paramsX, limit, datasetId);
    }

    const k = Math.max(1, Number(options.groundingK ?? 10));
    const minSim = Number(options.minSim ?? 0.78);
    const g = await groundQueryTags(plan, session, k, minSim);
    plan.grounding = g.grounding;
    if (!g.params.length) {
      throw new Error(
        `Prompt-tag grounding produced no corpus matches (k=${k}, minSim=${minSim.toFixed(2)}). ` +
        `Either the prompt is off-corpus, the similarity floor is too high, or :Tag embeddings ` +
        `are missing — run \`python -m tagging embed-tags\` against the herb database.`,
      );
    }
    const result = await session.run(scoreCypher(clauseX), {
      queryTags: g.params,
      activeFacets: facets,
      minWChunk: Number(options.minWChunk ?? plan.filters.min_w_chunk ?? 0),
      minRelevanceToFile: Number(options.minRelevanceToFile ?? plan.filters.min_relevance_to_file ?? 0),
      limit: neo4j.int(limit),
      datasetId,
      runId: DONE_GRAPH_RUN_ID,
      ...paramsX,
    });
    // The year constraint is enforced by the hard gate (c.years, projected
    // from the model-curated temporal tags) — no full-text union here. The
    // earlier union existed to compensate for the regex-scraped years and is
    // gone with it; lexical full-text remains only for the no-tags path above.
    return rowsToChunks(result.records);
  });
}

export async function retrieveBaseline(
  limit: number, cfg: Neo4jConfig, datasetId: string | null = null, gate: HardGate = EMPTY_GATE,
): Promise<RetrievedChunk[]> {
  const { clause, params: gateParams } = buildGate(gate);
  return withSession(cfg, async (session) => {
    const result = await session.run(baselineCypher(clause), {
      limit: neo4j.int(limit), datasetId, ...gateParams,
    });
    return rowsToChunks(result.records);
  });
}
