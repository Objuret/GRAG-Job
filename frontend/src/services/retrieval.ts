import neo4j from 'neo4j-driver';
import type { FacetDimension } from '../types';
import type { Neo4jConfig } from './neo4j';
import type { QueryPlan, QueryTag } from './interpreter';
import { intVal, withSession } from './neo4j';
import { embedPromptTags } from './embeddings';

const TAG_VECTOR_INDEX = 'tag_embedding';

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
  groundTags?: boolean;     // default true; false → legacy exact-name match
  groundingK?: number;      // nearest corpus tags per prompt tag (default 10)
  minSim?: number;          // drop matches below this cosine sim (default 0.78)
}

// Weighted overlap, with the grounding similarity folded in:
// score = Σ qt.w_query * qt.facets[edge.facet] * edge.w_chunk * edge.w_facet
//           * coalesce(chunk.relevance_to_file, 1) * coalesce(qt.sim, 1)
// Query tags are grounded corpus :Tag names (qt.name); an exact-name fallback
// passes sim = 1.0 so the same Cypher serves both paths.
const SCORE_CYPHER = `
UNWIND $queryTags AS qt
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
MATCH (c)-[r:HAS_TAG]->(t:Tag {name: qt.name})
WHERE coalesce(c.empty, false) = false
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
  AND r.run_id = $runId
  AND r.facet IN $activeFacets
  AND coalesce(r.w_chunk, 0.0) >= $minWChunk
  AND coalesce(c.relevance_to_file, 1.0) >= $minRelevanceToFile
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
         * coalesce(qt.sim, 1.0)) AS score
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

const BASELINE_CYPHER = `
MATCH (f:File)-[:HAS_CHUNK]->(c:Chunk)
WHERE coalesce(c.empty, false) = false
  AND c.relevance_to_file IS NOT NULL
  AND ($datasetId IS NULL OR f.dataset_id = $datasetId)
RETURN c.chunk_id   AS chunkId,
       c.file_id    AS fileId,
       c.content    AS content,
       c.description AS description,
       c.relevance_to_file AS relevanceToFile,
       c.relevance_to_file AS score
ORDER BY c.relevance_to_file DESC
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
  name: string;          // corpus :Tag name to match
  sim: number;           // grounding confidence (1.0 for exact-name)
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

/** Legacy path: exact cleaned-name match, sim fixed at 1.0. */
function toExactParams(tags: QueryTag[]): ScoreTagParam[] {
  return tags.map(qt => ({ name: qt.t, sim: 1.0, ...facetCols(qt) }));
}

/**
 * Grounding: embed each prompt tag (e5 `query:`) and kNN against the
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
  const vectors = await embedPromptTags(plan.tags.map(t => t.t));
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

export async function retrieveChunks(plan: QueryPlan, cfg: Neo4jConfig, options: RetrievalOptions = {}): Promise<RetrievedChunk[]> {
  const limit = retrievalLimit(plan, options);
  const datasetId = retrievalDataset(plan, options);
  const facets = activeFacets(options);
  if (options.strategy === 'relevance') return retrieveBaseline(limit, cfg, datasetId);
  if (options.tagsEnabled === false) return retrieveBaseline(limit, cfg, datasetId);
  if (!plan.tags.length || !facets.length) return [];
  const ground = options.groundTags !== false;
  const k = Math.max(1, Number(options.groundingK ?? 10));
  const minSim = Number(options.minSim ?? 0.78);
  return withSession(cfg, async (session) => {
    let queryTags: ScoreTagParam[];
    if (ground) {
      try {
        const g = await groundQueryTags(plan, session, k, minSim);
        plan.grounding = g.grounding;
        // Fall back to exact-name if grounding produced no usable matches
        // (e.g. embeddings not yet written) so retrieval still functions.
        queryTags = g.params.length ? g.params : toExactParams(plan.tags);
      } catch {
        queryTags = toExactParams(plan.tags);
      }
    } else {
      queryTags = toExactParams(plan.tags);
    }
    const result = await session.run(SCORE_CYPHER, {
      queryTags,
      activeFacets: facets,
      minWChunk: Number(options.minWChunk ?? plan.filters.min_w_chunk ?? 0),
      minRelevanceToFile: Number(options.minRelevanceToFile ?? plan.filters.min_relevance_to_file ?? 0),
      limit: neo4j.int(limit),
      datasetId,
      runId: DONE_GRAPH_RUN_ID,
    });
    return result.records.map(rec => {
      const obj: Record<string, unknown> = {};
      for (const key of rec.keys) obj[key as string] = rec.get(key as string);
      return rowToChunk(obj);
    });
  });
}

export async function retrieveBaseline(limit: number, cfg: Neo4jConfig, datasetId: string | null = null): Promise<RetrievedChunk[]> {
  return withSession(cfg, async (session) => {
    const result = await session.run(BASELINE_CYPHER, { limit: neo4j.int(limit), datasetId });
    return result.records.map(rec => {
      const obj: Record<string, unknown> = {};
      for (const key of rec.keys) obj[key as string] = rec.get(key as string);
      return rowToChunk(obj);
    });
  });
}
