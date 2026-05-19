import { chat } from './llm';

export interface FacetScores {
  topic: number;
  entities: number;
  activity: number;
  temporal: number;
  evidence: number;
}

export interface QueryTag {
  t: string;
  facets: FacetScores;
  w_query: number;
}

/**
 * Hard structured constraints, applied as a deterministic gate BEFORE any
 * tag/embedding scoring (see retrieval.ts). Values map to materialized
 * `:Chunk` properties written by `python -m tagging materialize`. Only set
 * when the user's query explicitly names the constraint; retrieval validates
 * each value against the live corpus enum and FAILS LOUD on an unknown value
 * (no silent "ignore the filter and scan everything" fallback).
 */
export interface HardGate {
  product: string | null;
  section: string | null;
  channel: string | null;
  employee_id: string | null;
  years: number[];
}

export interface QueryFilters {
  dataset_id: string | null;
  file_ids: string[];
  min_w_chunk: number;
  min_relevance_to_file: number;
  limit: number;
  gate: HardGate;
}

/** Per prompt tag, the corpus :Tag names it grounded to (vector kNN). */
export interface PlanGrounding {
  promptTag: string;
  matches: { name: string; sim: number }[];
}

export interface QueryPlan {
  description: string;
  tags: QueryTag[];
  filters: QueryFilters;
  answer_job: {
    mode: string;
    evidence_policy: string;
    missing_evidence_policy: string;
  };
  warnings: string[];
  /** Set by retrieval's grounding step; shown beside results in the UI. */
  grounding?: PlanGrounding[];
}

const FILLER = new Set(['data', 'information', 'content', 'record', 'text', 'chunk', 'item', 'find']);
const COVERAGE_ALPHA = 0.25;

function cleanTag(raw: string): string {
  return raw.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function computeWQuery(facets: FacetScores): number {
  const vals = Object.values(facets);
  const n = vals.length;
  const s = vals.reduce((a, b) => a + b, 0);
  const s2 = vals.reduce((a, b) => a + b * b, 0);
  if (s2 === 0) return 0;
  const strength = Math.sqrt(s2 / n);
  const coverageBonus = Math.pow((s * s) / (n * s2), COVERAGE_ALPHA);
  return Math.round(strength * coverageBonus * 100) / 100;
}

/**
 * Find the first balanced `{ ... }` block, ignoring braces inside strings and
 * escaped characters. Tolerates leading prose, trailing prose, and code fences.
 */
function extractJson(text: string): unknown {
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fence ? fence[1].trim() : text;

  const start = body.indexOf('{');
  if (start === -1) throw new Error('No JSON object found in model output: ' + text.slice(0, 200));

  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < body.length; i++) {
    const ch = body[i];
    if (escape) { escape = false; continue; }
    if (ch === '\\' && inString) { escape = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return JSON.parse(body.slice(start, i + 1));
    }
  }
  throw new Error('Unterminated JSON object in model output: ' + text.slice(0, 200));
}

const EMPTY_GATE: HardGate = {
  product: null, section: null, channel: null, employee_id: null, years: [],
};
const DEFAULT_FILTERS: QueryFilters = {
  dataset_id: null, file_ids: [], min_w_chunk: 0, min_relevance_to_file: 0, limit: 20,
  gate: EMPTY_GATE,
};

const GATE_SECTIONS = [
  'slack', 'documents', 'meeting_transcripts', 'meeting_chats', 'prs',
  'urls', 'answerable_questions', 'unanswerable_questions', 'product_profile',
];

/** Normalise the model's loose gate object into a strict HardGate. */
function parseGate(raw: unknown): HardGate {
  const g = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const str = (v: unknown): string | null =>
    typeof v === 'string' && v.trim() ? v.trim() : null;
  const section = str(g.section);
  const years = Array.isArray(g.years)
    ? [...new Set(g.years.map(Number).filter(y => Number.isInteger(y) && y >= 1000 && y <= 9999))]
    : [];
  return {
    product: str(g.product),
    section: section && GATE_SECTIONS.includes(section) ? section : null,
    channel: str(g.channel),
    employee_id: str(g.employee_id),
    years,
  };
}
const DEFAULT_ANSWER_JOB = {
  mode: 'direct_answer',
  evidence_policy: 'retrieved_only',
  missing_evidence_policy: 'say_insufficient_evidence',
};

export async function interpretPrompt(
  prompt: string,
  model: string,
  openaiKey: string,
  anthropicKey: string,
  datasetId: string | null = null,
  temperature?: number,
): Promise<QueryPlan> {
  const call = (messages: Parameters<typeof chat>[0], maxTokens: number) =>
    chat(messages, model, openaiKey, anthropicKey, {
      maxTokens,
      jsonMode: true,
      ...(temperature != null ? { temperature } : {}),
    });

  // Pass 1 — describe the information need first, then derive tags from it.
  // The description is not incidental: it becomes the prompt-side embedding
  // context (mirroring corpus chunk descriptions), so it must be a faithful,
  // self-contained statement of what the user wants to find.
  const p1 = await call([
    {
      role: 'system',
      content:
        'You interpret a user query for graph retrieval. Work in two steps. ' +
        'STEP 1: write "description" — a concise, self-contained 1–3 sentence statement of the ' +
        'underlying information need (what the user actually wants to find, including implied entities/scope), ' +
        'in plain declarative prose, not a restatement of the question. ' +
        'STEP 2: derive "tags" FROM that description — specific noun phrases, named entities, systems, or actions. ' +
        'No generic filler words. ' +
        'STEP 3: extract "gate" — hard structured constraints ONLY when the query explicitly names them, else null/[]. ' +
        'Fields: product (a "*Force"/"*Genie"-style product name if named), ' +
        `section (one of: ${GATE_SECTIONS.join(', ')} — map synonyms, e.g. "pull requests"->prs, "chat"->slack), ` +
        'channel (a Slack channel name if given), employee_id (an "eid_..." id if given), ' +
        'years (array of 4-digit years explicitly mentioned). ' +
        'Do NOT guess values that are not in the query. ' +
        'Return ONLY valid JSON: {"description":"...","tags":["tag1"],"gate":{"product":null,"section":null,"channel":null,"employee_id":null,"years":[]}}.',
    },
    { role: 'user', content: `User query: ${prompt}` },
  ], 512);

  const p1json = extractJson(p1.text) as { description?: string; tags?: string[]; gate?: unknown };
  const gate = parseGate(p1json.gate);
  const rawTags = (p1json.tags ?? []).map(cleanTag).filter(t => t.length > 1 && !FILLER.has(t));
  const description = p1json.description ?? prompt;

  if (!rawTags.length) {
    return {
      description,
      tags: [],
      filters: { ...DEFAULT_FILTERS, dataset_id: datasetId, gate },
      answer_job: DEFAULT_ANSWER_JOB,
      warnings: ['No tags extracted from prompt — try a more specific query.'],
    };
  }

  // Pass 2 — score each tag against 5 facets
  const p2 = await call([
    {
      role: 'system',
      content:
        'Score retrieval tags against five facets (each 0.0–1.0). ' +
        'topic: subject matter. entities: named people/orgs/products/systems. ' +
        'activity: events/processes/actions. temporal: time relevance. evidence: answer material type. ' +
        'Return ONLY valid JSON: {"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}',
    },
    {
      role: 'user',
      content: `Original query: ${prompt}\n\nScore these tags:\n${JSON.stringify(rawTags)}`,
    },
  ], 1024);

  const p2json = extractJson(p2.text) as { scores?: Array<{ t: string; facets: FacetScores }> };
  const scoreMap = new Map((p2json.scores ?? []).map(s => [s.t, s.facets]));

  const tags: QueryTag[] = rawTags.map(t => {
    const facets = scoreMap.get(t) ?? { topic: 0.2, entities: 0.2, activity: 0.2, temporal: 0.2, evidence: 0.2 };
    return { t, facets, w_query: computeWQuery(facets) };
  });

  return {
    description,
    tags,
    filters: { ...DEFAULT_FILTERS, dataset_id: datasetId, gate },
    answer_job: DEFAULT_ANSWER_JOB,
    warnings: [],
  };
}
