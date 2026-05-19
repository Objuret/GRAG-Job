import neo4j from 'neo4j-driver';
import type { FacetDimension } from '../types';
import type { Neo4jConfig } from './neo4j';
import type { HardGate, QueryPlan, QueryTag } from './interpreter';
import { intVal, withSession } from './neo4j';
import { embedPromptTagFacets, type EmbedFacet, type PromptTagFacetInput } from './embeddings';

// One native vector index per facet, on :Tag(emb_<facet>). The grounding
// vectors are tag properties — there are no companion embedding nodes.
const TAG_VECTOR_INDEX: Record<EmbedFacet, string> = {
  topic: 'tag_emb_topic',
  entities: 'tag_emb_entities',
  activity: 'tag_emb_activity',
  temporal: 'tag_emb_temporal',
  evidence: 'tag_emb_evidence',
  all: 'tag_emb_all',
};
const CHUNK_FULLTEXT_INDEX = 'chunk_fulltext';
const CONTENT_FULLTEXT_INDEX = 'chunk_content_ft';

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
        `Valid ${f} values: ${valid.length ? valid.join(', ') : '(none materialized — run `python -m tagging materialize`)'}.`,
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

/**
 * A selected dataset that matches zero files is a loud error listing the
 * valid dataset ids — never a silent "scan/return nothing". Mirrors the
 * hard-gate validation philosophy.
 */
async function validateDataset(session: Session, datasetId: string | null): Promise<void> {
  if (!datasetId) return;
  const res = await session.run(
    'MATCH (f:File) WHERE f.dataset_id = $datasetId RETURN count(f) AS n',
    { datasetId },
  );
  if ((intVal(res.records[0]?.get('n')) ?? 0) > 0) return;
  const enumRes = await session.run(
    `MATCH (f:File) WHERE f.dataset_id IS NOT NULL
     RETURN DISTINCT f.dataset_id AS v ORDER BY v LIMIT 60`,
  );
  const valid = enumRes.records.map(r => r.get('v') as string);
  throw new Error(
    `Dataset "${datasetId}" matches no files in the graph. ` +
    `Valid datasets: ${valid.length ? valid.join(', ') : '(none — the graph has no :File nodes)'}.`,
  );
}

/** One prompt tag → the corpus :Tag names it grounded to, with cosine sim. */
export interface GroundedTag {
  promptTag: string;
  matches: { name: string; facet: EmbedFacet; sim: number }[];
}

export interface RetrievedChunk {
  chunkId: string;
  fileId: string;
  content: string;
  description: string | null;
  relevanceToFile: number | null;
  score: number;
}

const DEFAULT_GRAPH_RUN_ID = 'pilot_full_herb';
const ALL_FACETS: FacetDimension[] = ['topic', 'entities', 'activity', 'temporal', 'evidence'];
const DEFAULT_EXCLUDED_SECTIONS = ['answerable_questions', 'unanswerable_questions', 'product_profile'];

const EMPTY_GATE: HardGate = {
  product: null, section: null, channel: null, employee_id: null, years: [],
};

function gateOf(plan: QueryPlan): HardGate {
  return plan.filters?.gate ?? EMPTY_GATE;
}

export type RetrievalStrategy = 'weighted' | 'relevance';

export interface RetrievalInputOptions {
  activeFacets?: FacetDimension[];
  tagsEnabled?: boolean;
  minWChunk?: number;
  minRelevanceToFile?: number;
  limit?: number;
  datasetId?: string | null;
  runId?: string;
  strategy?: RetrievalStrategy | string;
  /** Tag-grounding knobs (the interpreter "effort" control). */
  groundingK?: number;      // nearest corpus tags per prompt tag (default 10)
  minSim?: number;          // drop matches below this cosine sim (default 0.78)
  /** RAG-eval leakage guard: QA records + oracle product profiles are excluded by default. */
  excludedSections?: string[];
}

export interface RetrievalInput {
  /** LLM-produced query interpretation; retrieval never asks the model again. */
  plan: QueryPlan;
  /** Deterministic graph scope for every Cypher path. */
  scope: {
    datasetId: string | null;
    runId: string;
  };
  /** Deterministic controls from the retrieval lane UI. */
  controls: {
    strategy: RetrievalStrategy;
    activeFacets: FacetDimension[];
    tagsEnabled: boolean;
    limit: number;
    minWChunk: number;
    minRelevanceToFile: number;
    groundingK: number;
    minSim: number;
    excludedSections: string[];
  };
  /** Hard structured gate from the plan, validated before tag scoring. */
  gate: HardGate;
}

function excludedSections(options?: RetrievalInputOptions): string[] {
  return [...new Set((options?.excludedSections ?? DEFAULT_EXCLUDED_SECTIONS).filter(Boolean))];
}

function exclusionClause(excluded: string[]): string {
  return excluded.length ? 'AND NOT (coalesce(c.section, "") IN $excludedSections)' : '';
}

function sanitizeLucene(text: string): string {
  return text.replace(/[+\-&|!(){}[\]^"~*?:\\/]/g, ' ').replace(/\s+/g, ' ').trim();
}

function validateEvalScope(gate: HardGate, excluded: string[]): void {
  if (gate.section && excluded.includes(gate.section)) {
    throw new Error(
      `Section "${gate.section}" is excluded from RAG-safe retrieval. ` +
      `Eval exclusions: ${excluded.join(', ')}.`,
    );
  }
}

// Weighted overlap, with the grounding similarity folded in:
// score = Σ qt.w_query * qt.facets[edge.facet] * edge.w_chunk * edge.w_facet
//           * coalesce(chunk.relevance_to_file, 1) * qt.sim
// Query tags are always grounded corpus :Tag names (qt.name) with a real
// cosine sim. There is no exact-name path.
const scoreCypher = (gate: string, exclude: string) => `
UNWIND $queryTags AS qt
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[r:HAS_TAG]->(t:Tag {name: qt.name})
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND r.facet IN $activeFacets
  AND (qt.facet = 'all' OR r.facet = qt.facet)
  AND coalesce(r.w_chunk, 0.0) >= $minWChunk
  AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
  ${gate}
  ${exclude}
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
         * qt.sim
         * coalesce(qt.scopeWeight, 1.0)) AS score
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

const baselineCypher = (gate: string, exclude: string) => `
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND c.relevance_to_file IS NOT NULL
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  ${gate}
  ${exclude}
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
const lexicalCypher = (gate: string, exclude: string) => `
CALL db.index.fulltext.queryNodes($idx, $q) YIELD node AS c, score AS lex
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  ${gate}
  ${exclude}
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
  facet: EmbedFacet;     // grounded corpus embedding facet; 'all' can score any edge facet
  sim: number;           // grounding cosine similarity
  scopeWeight: number;   // lower for the broad 'all' embedding
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
 * side — see embeddings.ts) and kNN against the per-facet `tag_emb_<facet>`
 * vector index (the grounding vectors are :Tag properties) to expand it onto
 * real corpus (tag, facet) uses. Each grounded name inherits the prompt tag's
 * facet vector + w_query and carries the cosine sim, which the scorer folds
 * into the weight.
 */
async function groundQueryTags(
  plan: QueryPlan,
  session: Parameters<Parameters<typeof withSession>[1]>[0],
  k: number,
  minSim: number,
  activeFacets: FacetDimension[],
): Promise<{ params: ScoreTagParam[]; grounding: GroundedTag[] }> {
  const requests: Array<PromptTagFacetInput & { promptIndex: number; scopeWeight: number }> = [];
  for (let i = 0; i < plan.tags.length; i++) {
    const qt = plan.tags[i];
    for (const facet of activeFacets) {
      if ((qt.facets[facet] ?? 0) <= 0) continue;
      requests.push({ promptIndex: i, name: qt.t, facet, scopeWeight: 1.0 });
    }
    requests.push({ promptIndex: i, name: qt.t, facet: 'all', scopeWeight: 0.65 });
  }

  const vectors = await embedPromptTagFacets(requests, plan.description);
  const params: ScoreTagParam[] = [];
  const grounding: GroundedTag[] = plan.tags.map(qt => ({ promptTag: qt.t, matches: [] }));

  for (let i = 0; i < requests.length; i++) {
    const req = requests[i];
    const qt = plan.tags[req.promptIndex];
    const vec = vectors[i];
    if (!vec) continue;
    const queryK = Math.max(k * 20, 200);
    const res = await session.run(
      `CALL db.index.vector.queryNodes($idx, $k, $vec) YIELD node, score
       RETURN node.name AS name, score AS sim`,
      { idx: TAG_VECTOR_INDEX[req.facet], k: neo4j.int(Math.max(1, queryK)), vec },
    );
    let accepted = 0;
    for (const rec of res.records) {
      const name = rec.get('name') as string;
      const facet = req.facet;
      const sim = Number(rec.get('sim'));
      if (!name || !facet || !Number.isFinite(sim) || sim < minSim) continue;
      const rounded = Math.round(sim * 1e4) / 1e4;
      grounding[req.promptIndex].matches.push({ name, facet, sim: rounded });
      params.push({ name, facet, sim, scopeWeight: req.scopeWeight, ...facetCols(qt) });
      accepted += 1;
      if (accepted >= k) break;
    }
  }

  for (const g of grounding) {
    const seen = new Set<string>();
    g.matches = g.matches
      .sort((a, b) => b.sim - a.sim)
      .filter((m) => {
        const key = `${m.name}|${m.facet}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, k);
  }
  return { params, grounding };
}

function retrievalLimit(plan: QueryPlan, options?: RetrievalInputOptions): number {
  const raw = Number(options?.limit ?? plan.filters.limit ?? 20);
  return Math.max(1, Math.min(500, Number.isFinite(raw) ? raw : 20));
}

function retrievalDataset(plan: QueryPlan, options?: RetrievalInputOptions): string | null {
  return options?.datasetId ?? plan.filters.dataset_id ?? null;
}

function activeFacets(options?: RetrievalInputOptions): FacetDimension[] {
  if (!options?.activeFacets) return ALL_FACETS;
  return options.activeFacets.filter((f): f is FacetDimension => ALL_FACETS.includes(f as FacetDimension));
}

function retrievalStrategy(value: RetrievalInputOptions['strategy']): RetrievalStrategy {
  return value === 'relevance' ? 'relevance' : 'weighted';
}

export function buildRetrievalInput(plan: QueryPlan, options: RetrievalInputOptions = {}): RetrievalInput {
  const gate = gateOf(plan);
  return {
    plan,
    scope: {
      datasetId: retrievalDataset(plan, options),
      runId: options.runId ?? DEFAULT_GRAPH_RUN_ID,
    },
    controls: {
      strategy: retrievalStrategy(options.strategy),
      activeFacets: activeFacets(options),
      tagsEnabled: options.tagsEnabled ?? true,
      limit: retrievalLimit(plan, options),
      minWChunk: Number(options.minWChunk ?? plan.filters.min_w_chunk ?? 0),
      minRelevanceToFile: Number(options.minRelevanceToFile ?? plan.filters.min_relevance_to_file ?? 0),
      groundingK: Math.max(1, Number(options.groundingK ?? 10)),
      minSim: Number(options.minSim ?? 0.78),
      excludedSections: excludedSections(options),
    },
    gate: { ...gate, years: [...gate.years] },
  };
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
  session: Session, plan: QueryPlan, gateClause: string, excludeClause: string,
  gateParams: Record<string, unknown>, excluded: string[], limit: number, datasetId: string | null,
): Promise<RetrievedChunk[]> {
  const q = buildLexQuery(plan);
  if (!q) return [];
  const res = await session.run(lexicalCypher(gateClause, excludeClause), {
    idx: CHUNK_FULLTEXT_INDEX, q, limit: neo4j.int(limit), datasetId,
    excludedSections: excluded, ...gateParams,
  });
  return rowsToChunks(res.records);
}

/** Outcome of the `ground` node: which retrieval path applies, plus the
 *  grounded corpus-tag params the `retrieve_tags` node will score with. */
export interface GroundResult {
  grounding: GroundedTag[];
  params: ScoreTagParam[];
  path: 'weighted' | 'lexical' | 'empty';
}

/**
 * The `ground` pipeline node: validate dataset + hard gate, then embed the
 * prompt tags and kNN them onto corpus `:Tag`s. Returns the grounded params
 * for `scoreGroundedChunks`; no chunk scoring happens here.
 */
export async function groundRetrieval(
  input: RetrievalInput, cfg: Neo4jConfig,
): Promise<GroundResult> {
  const { plan, scope, controls, gate } = input;
  const datasetId = scope.datasetId;
  const facets = controls.activeFacets;
  const { active: gated } = buildGate(gate);
  validateEvalScope(gate, controls.excludedSections);

  return withSession(cfg, async (session) => {
    // A dataset that contains no files is a loud error, not an empty result.
    await validateDataset(session, datasetId);
    // Hard gate is validated up-front: an unknown constraint value is a loud
    // error, never a silent "ignore it and scan everything".
    if (gated) await validateGate(session, gate, datasetId);

    const haveTags = plan.tags.length > 0 && facets.length > 0;

    // No usable tags but a hard constraint exists → the structured query is
    // still answerable via the gated lexical path. This is the intended
    // structured route, not a degradation; surface it as a warning so it is
    // never silent.
    if (!haveTags) {
      if (!gated) return { grounding: [], params: [], path: 'empty' };
      plan.warnings.push('No tags from prompt — answered via the hard-gate + full-text path only.');
      return { grounding: [], params: [], path: 'lexical' };
    }

    const k = controls.groundingK;
    const minSim = controls.minSim;
    const g = await groundQueryTags(plan, session, k, minSim, facets);
    plan.grounding = g.grounding;
    if (!g.params.length) {
      throw new Error(
        `Prompt-tag grounding produced no corpus matches (k=${k}, minSim=${minSim.toFixed(2)}). ` +
        `Either the prompt is off-corpus, the similarity floor is too high, or :Tag embeddings ` +
        `are missing — run \`python -m tagging embed-tags\` against the target database.`,
      );
    }
    return { grounding: g.grounding, params: g.params, path: 'weighted' };
  });
}

/**
 * Score the chunks for an already-grounded retrieval. Separated from
 * grounding so the canvas can run `ground` and `retrieve_tags` as distinct
 * nodes (and splice a probe between them) — the weighted-overlap Cypher is
 * unchanged. `empty` → no rows; `lexical` → the gated full-text path.
 */
export async function scoreGroundedChunks(
  input: RetrievalInput, cfg: Neo4jConfig, ground: GroundResult,
): Promise<RetrievedChunk[]> {
  const { plan, scope, controls, gate } = input;
  const { clause, params: gateParams } = buildGate(gate);
  const exclude = exclusionClause(controls.excludedSections);
  validateEvalScope(gate, controls.excludedSections);
  if (ground.path === 'empty') return [];
  return withSession(cfg, async (session) => {
    if (ground.path === 'lexical') {
      return runLexical(
        session, plan, clause, exclude, gateParams, controls.excludedSections,
        controls.limit, scope.datasetId,
      );
    }
    const result = await session.run(scoreCypher(clause, exclude), {
      queryTags: ground.params,
      activeFacets: controls.activeFacets,
      minWChunk: controls.minWChunk,
      minRelevanceToFile: controls.minRelevanceToFile,
      limit: neo4j.int(controls.limit),
      datasetId: scope.datasetId,
      runId: scope.runId,
      excludedSections: controls.excludedSections,
      ...gateParams,
    });
    // The year constraint is enforced by the hard gate (c.years, projected
    // from the model-curated temporal tags) — no full-text union here.
    const scored = rowsToChunks(result.records);
    if (scored.length > 0) return scored;

    plan.warnings.push(
      'Tag-scored retrieval returned no chunks under the gate — fell back to the hard-gate + full-text recall path.',
    );
    return runLexical(
      session, plan, clause, exclude, gateParams, controls.excludedSections,
      controls.limit, scope.datasetId,
    );
  });
}

/**
 * Always-present gate parameters for the module-Cypher path. Unlike
 * `buildGate` (which injects clause strings), the user-authored / default
 * module query uses null-tolerant predicates, so every gate field is bound
 * (null / [] when unset) and the query decides how to apply it.
 */
function gateBindings(gate: HardGate): Record<string, unknown> {
  return {
    g_product: gate.product ?? null,
    g_section: gate.section ?? null,
    g_channel: gate.channel ?? null,
    g_employee_id: gate.employee_id ?? null,
    g_years: gate.years.map((y) => neo4j.int(y)),
  };
}

const MODULE_RETURN_COLUMNS = [
  'chunkId', 'fileId', 'content', 'description', 'relevanceToFile', 'score',
] as const;

async function assertNoExcludedChunks(
  session: Session, chunks: RetrievedChunk[], excluded: string[],
): Promise<void> {
  if (!chunks.length || !excluded.length) return;
  const res = await session.run(
    `
    MATCH (c:Chunk)
    WHERE c.chunk_id IN $chunkIds AND c.section IN $excludedSections
    RETURN c.chunk_id AS chunkId, c.section AS section
    ORDER BY chunkId
    LIMIT 5
    `,
    { chunkIds: chunks.map(c => c.chunkId), excludedSections: excluded },
  );
  if (!res.records.length) return;
  const hits = res.records.map(r => `${r.get('chunkId')}(${r.get('section')})`).join(', ');
  throw new Error(
    `Retrieval returned chunk(s) from RAG-eval excluded sections: ${hits}. ` +
    `Fix the query module or target database.`,
  );
}

/**
 * Execute a Query-module's composed Cypher as the real retrieval query
 * (Lane A, weighted path). The module text is run verbatim with the canonical
 * bindings; dataset + hard gate are validated loudly up-front, and the result
 * contract is enforced loudly — a module that doesn't RETURN the required
 * columns is an error, never a silently dropped result.
 */
export async function runModuleCypher(
  input: RetrievalInput, cfg: Neo4jConfig, ground: GroundResult, cypherText: string,
): Promise<RetrievedChunk[]> {
  const { plan, scope, controls, gate } = input;
  if (!cypherText.trim()) {
    throw new Error('Query module is wired into retrieval but composed no Cypher (empty fragment chain).');
  }
  if (ground.path !== 'weighted') {
    // No grounded tags → the weighted module query has nothing to score.
    // Fall back to the standard grounded path, which handles empty/lexical
    // loudly via its own contract (never a silent empty here).
    return scoreGroundedChunks(input, cfg, ground);
  }
  validateEvalScope(gate, controls.excludedSections);
  return withSession(cfg, async (session) => {
    await validateDataset(session, scope.datasetId);
    if (buildGate(gate).active) await validateGate(session, gate, scope.datasetId);
    const result = await session.run(cypherText, {
      plan,
      queryTags: ground.params,
      activeFacets: controls.activeFacets,
      minWChunk: controls.minWChunk,
      minRelevanceToFile: controls.minRelevanceToFile,
      limit: neo4j.int(controls.limit),
      datasetId: scope.datasetId,
      runId: scope.runId,
      excludedSections: controls.excludedSections,
      ...gateBindings(gate),
    });
    if (result.records.length) {
      const keys = result.records[0].keys.map(String);
      const missing = MODULE_RETURN_COLUMNS.filter((c) => !keys.includes(c));
      if (missing.length) {
        throw new Error(
          `Query module Cypher is missing required RETURN column(s): ${missing.join(', ')}. ` +
          `It returned [${keys.join(', ')}]. The module must RETURN ${MODULE_RETURN_COLUMNS.join(', ')} ` +
          `(see the default module header/footer for the canonical shape).`,
        );
      }
    }
    const chunks = rowsToChunks(result.records);
    await assertNoExcludedChunks(session, chunks, controls.excludedSections);
    return chunks;
  });
}

export async function retrieveBaseline(
  input: RetrievalInput, cfg: Neo4jConfig,
): Promise<RetrievedChunk[]> {
  const { scope, controls, gate } = input;
  const { clause, params: gateParams } = buildGate(gate);
  const exclude = exclusionClause(controls.excludedSections);
  validateEvalScope(gate, controls.excludedSections);
  return withSession(cfg, async (session) => {
    await validateDataset(session, scope.datasetId);
    const result = await session.run(baselineCypher(clause, exclude), {
      limit: neo4j.int(controls.limit), datasetId: scope.datasetId,
      excludedSections: controls.excludedSections, ...gateParams,
    });
    return rowsToChunks(result.records);
  });
}

/**
 * Eval-only conventional baseline for RQ2.
 *
 * This is intentionally not the workbench Lane B `relevance_to_file` baseline:
 * it uses a plain Lucene full-text query over raw `c.content` only. No tags,
 * no prompt interpretation, no grounding, no hard gate, no file-relevance
 * prior. The graph is only a chunk store here. The same eval section
 * exclusions may still be applied so the baseline cannot read gold QA records.
 *
 * Requires a one-time index in the target DB:
 *   CREATE FULLTEXT INDEX chunk_content_ft IF NOT EXISTS
 *   FOR (c:Chunk) ON EACH [c.content];
 */
export async function retrieveBaselineContent(
  question: string,
  cfg: Neo4jConfig,
  options: { limit?: number; datasetId?: string | null; excludedSections?: string[] } = {},
): Promise<RetrievedChunk[]> {
  const q = sanitizeLucene(question);
  if (!q) return [];
  const limit = Math.max(1, Math.min(500, Number(options.limit ?? 20)));
  const datasetId = options.datasetId ?? null;
  const excluded = [...new Set((options.excludedSections ?? DEFAULT_EXCLUDED_SECTIONS).filter(Boolean))];
  const exclude = exclusionClause(excluded);
  const cypher = `
CALL db.index.fulltext.queryNodes($idx, $q) YIELD node AS c, score AS lex
MATCH (f:File)-[:HAS_CHUNK]->(c)
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  ${exclude}
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       round(lex, 4) AS score
ORDER BY lex DESC
LIMIT $limit
`;
  return withSession(cfg, async (session) => {
    await validateDataset(session, datasetId);
    try {
      const result = await session.run(cypher, {
        idx: CONTENT_FULLTEXT_INDEX,
        q,
        limit: neo4j.int(limit),
        datasetId,
        excludedSections: excluded,
      });
      return rowsToChunks(result.records);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (/no such (fulltext schema )?index|chunk_content_ft/i.test(msg)) {
        throw new Error(
          `Baseline content index '${CONTENT_FULLTEXT_INDEX}' is missing. Create it once: ` +
          `CREATE FULLTEXT INDEX ${CONTENT_FULLTEXT_INDEX} IF NOT EXISTS ` +
          `FOR (c:Chunk) ON EACH [c.content]; then CALL db.awaitIndexes().`,
        );
      }
      throw err;
    }
  });
}
