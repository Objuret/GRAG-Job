/** Shared RAGAS export contract — browser + headless + Python scorer. */

export const RAGAS_EXPORT_SCHEMA = 'ragas-export/v1' as const;

export type ExportArm = 'graph' | 'content' | 'relevance' | 'sql_agent';

export interface CohortItem {
  index: number;
  id: string;
  has_reference: boolean;
  /** Parsed from `gold_{qtype}_{product}_{ix}` when present. */
  qtype?: string;
  product?: string;
  item_index?: number;
}

export interface CohortManifest {
  source: string;
  count: number;
  items: CohortItem[];
  /** Optional sidecar from `build_gold_set` (`*.manifest.json`). */
  builder_manifest?: string | null;
}

export interface RunFrameInvocation {
  questions: string;
  out: string;
  config: string | null;
  max_questions: number;
  repeats: number;
  concurrency: number;
  flags: string[];
  permanent_skip_ids: string[];
}

export interface RunFrameResolved {
  arm: ExportArm;
  route_origin: string | null;
  label: string | null;
  database: string | null;
  run_id: string | null;
  dataset_id: string | null;
  models: { answer: string; interpret: string | null };
  prompt_mode: string | null;
  temperature: number;
  retrieval: Record<string, unknown>;
  evidence: {
    answer_max_chunks: number;
    answer_max_chunk_chars: number;
    answer_scrub: boolean;
  };
  exclude_sections: string[];
  neo4j_uri?: string | null;
  sql?: {
    db_path: string | null;
    max_tool_calls: number;
    max_rows_per_query: number;
    max_cell_chars: number;
    base_url?: string | null;
  };
}

export interface RunFrame {
  kind: 'run_frame';
  schema: typeof RAGAS_EXPORT_SCHEMA;
  exported_at: string;
  arm: ExportArm;
  route_origin: string | null;
  label: string | null;
  invocation: RunFrameInvocation;
  resolved: RunFrameResolved;
  cohort: CohortManifest;
  prompts?: Record<string, unknown>;
  config_source?: Record<string, unknown>;
}

export interface GoldQuestion {
  id: string;
  question: string;
  reference?: string;
}

export function isRunFrameRow(row: unknown): row is RunFrame {
  return !!row && typeof row === 'object' && (row as RunFrame).kind === 'run_frame';
}

/** HERB gold ids: `gold_{qtype}_{product}_{item_index}`. */
export function parseGoldId(id: string): Pick<CohortItem, 'qtype' | 'product' | 'item_index'> {
  const m = /^gold_([^_]+)_(.+)_(\d+)$/.exec(id);
  if (!m) return {};
  return { qtype: m[1], product: m[2], item_index: Number(m[3]) };
}

export function buildCohortManifest(
  sourcePath: string,
  items: GoldQuestion[],
  builderManifestPath: string | null = null,
): CohortManifest {
  return {
    source: sourcePath,
    count: items.length,
    builder_manifest: builderManifestPath,
    items: items.map((q, i) => ({
      index: i + 1,
      id: q.id,
      has_reference: !!(q.reference && q.reference.trim()),
      ...parseGoldId(q.id),
    })),
  };
}

/** Question rows carry per-item trace; static knobs live on `run_frame`. */
export function baseQuestionRow(
  id: string,
  question: string,
  reference: string | null | undefined,
): Record<string, unknown> {
  return {
    kind: 'question',
    id,
    question,
    user_input: question,
    reference: reference ?? null,
    answer: '',
    response: '',
    contexts: [] as string[],
    retrieved_contexts: [] as string[],
    meta: {} as Record<string, unknown>,
  };
}
