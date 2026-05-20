/**
 * Node-driven execution engine.
 *
 * The canvas is real: each executable node kind has one async executor, and a
 * lane runs by **topological order over its wired nodes/edges**. A node's
 * input is the output of its upstream node(s); values are typed and carry
 * their branch, so fork (A/B) and join (`compare`) need no positional
 * assumptions. A `probe` node is a typed passthrough — it records the value
 * flowing through and returns it unchanged, so it can be spliced anywhere a
 * type matches without altering the run.
 *
 * The service functions (`interpretPrompt`, `buildRetrievalInput`,
 * `groundRetrieval`, `scoreGroundedChunks`, `retrieveBaseline`,
 * `generateAnswer`) are unchanged — this module only orchestrates them in the
 * order the user wired, instead of a hardcoded sequence.
 */
import type { Neo4jConfig } from './neo4j';
import { interpretPrompt, type QueryPlan } from './interpreter';
import {
  buildRetrievalInput, groundRetrieval, scoreGroundedChunks, retrieveBaseline,
  retrieveBaselineContent, runModuleCypher,
  type RetrievalInput, type RetrievedChunk, type GroundResult,
} from './retrieval';
import { generateAnswer, type AnswerMode } from './answer';
import { composeModuleCypher } from '../query/queryModuleSyntax';
import type { ProviderKeys } from './llm';

// ─── Real metric helpers (computed from the actual run only) ────────────────
export interface NumStats { min: number; mean: number; max: number; n: number }

export function numStats(xs: number[]): NumStats | null {
  const v = xs.filter((n) => Number.isFinite(n));
  if (!v.length) return null;
  const sum = v.reduce((a, b) => a + b, 0);
  return { min: Math.min(...v), mean: sum / v.length, max: Math.max(...v), n: v.length };
}

export function laneChunkStats(chunks: RetrievedChunk[]) {
  return {
    count: chunks.length,
    score: numStats(chunks.map((c) => c.score)),
    rel: numStats(chunks.map((c) => c.relevanceToFile as number).filter((x) => x != null)),
    files: new Set(chunks.map((c) => c.fileId)).size,
  };
}

export function chunkSetOverlap(a: RetrievedChunk[], b: RetrievedChunk[]) {
  const sa = new Set(a.map((c) => c.chunkId));
  const sb = new Set(b.map((c) => c.chunkId));
  let inter = 0;
  for (const id of sa) if (sb.has(id)) inter += 1;
  const union = sa.size + sb.size - inter;
  return { count: inter, jaccard: union ? inter / union : 0 };
}

/** Distinct `[n]` / `[n,m]` chunk citations actually emitted by the answer. */
export function parseCitations(text: string, retrievedCount: number) {
  const ids = new Set<number>();
  let total = 0;
  const re = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text || ''))) {
    for (const part of m[1].split(',')) {
      const n = Number(part.trim());
      if (Number.isFinite(n)) { total += 1; ids.add(n); }
    }
  }
  return { total, distinct: ids.size, pctUsed: retrievedCount > 0 ? ids.size / retrievedCount : 0 };
}

export function groundingStats(grounding: QueryPlan['grounding']) {
  if (!grounding?.length) return null;
  const sims = grounding.flatMap((g) => g.matches.map((mm) => mm.sim));
  return {
    promptTags: grounding.length,
    groundedTags: grounding.reduce((n, g) => n + g.matches.length, 0),
    zeroGrounded: grounding.filter((g) => !g.matches.length).map((g) => g.promptTag),
    sim: numStats(sims),
  };
}

// ─── Engine types ───────────────────────────────────────────────────────────
export interface GraphNode {
  id: string;
  type?: string;
  parentId?: string;
  position?: { x: number; y: number };
  data?: Record<string, unknown> & { kind?: string };
}
export interface GraphEdge { id: string; source: string; target: string }

export interface RunEnv {
  prompt: string;
  connConfig: { model: string; keys: ProviderKeys };
  neo4jCfg: Neo4jConfig;
  runId: string;
  /** Full live canvas — a `querymodule` node composes its Cypher from its
   *  fragment children, which live in these arrays (not the lane node set). */
  nodes: GraphNode[];
  edges: GraphEdge[];
  log: (stage: string, status: 'running' | 'ok' | 'failed', message: string) => void;
}

/** Mutable run context shared across nodes (the plan the answer cites, the
 *  prompt mode, accumulated per-stage timing). */
interface RunCtx {
  prompt: string;
  mode: AnswerMode;
  plan: QueryPlan | null;
  retrievalInput: RetrievalInput | null;
  timing: Record<string, number | null>;
  start: number;
}

type Carried =
  | { t: 'prompt'; prompt: string; mode: AnswerMode }
  | { t: 'query_plan'; plan: QueryPlan }
  | { t: 'retrieval_input'; input: RetrievalInput }
  | { t: 'grounded'; input: RetrievalInput; ground: GroundResult; moduleCypher?: string }
  | { t: 'chunks'; branch: 'A' | 'B'; chunks: RetrievedChunk[] }
  | { t: 'answer'; branch: 'A' | 'B'; chunks: RetrievedChunk[]; response: string; tokensIn: number; tokensOut: number }
  | { t: 'result'; results: unknown; metrics: unknown };

type Executor = (
  inputs: Carried[], node: GraphNode, env: RunEnv, ctx: RunCtx,
) => Promise<Carried>;

const num = (v: unknown, d: number) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
};
const str = (v: unknown, d: string) => (typeof v === 'string' && v ? v : d);

function need<T extends Carried['t']>(inputs: Carried[], t: T): Extract<Carried, { t: T }> {
  const found = inputs.find((i) => i.t === t);
  if (!found) throw new Error(`pipeline: a node expected a "${t}" input but its upstream produced ${inputs.map((i) => i.t).join(', ') || 'nothing'}.`);
  return found as Extract<Carried, { t: T }>;
}

// ─── Per-kind executors ─────────────────────────────────────────────────────
const EXECUTORS: Record<string, Executor> = {
  prompt: async (_in, node, env, ctx) => {
    const mode = str(node.data?.mode, 'context') as AnswerMode;
    ctx.mode = mode;
    return { t: 'prompt', prompt: env.prompt, mode };
  },

  interpret: async (inputs, node, env, ctx) => {
    const p = need(inputs, 'prompt');
    const model = str(node.data?.model, env.connConfig.model);
    const datasetId = str(node.data?.datasetId, '') || null;
    env.log('interpret', 'running', `Interpreting prompt with ${model}.`);
    const t0 = Date.now();
    const plan = await interpretPrompt(
      p.prompt, model, env.connConfig.keys, datasetId,
    );
    ctx.timing.interpret = Date.now() - t0;
    env.log('interpret', 'ok', `Plan: ${plan.tags.length} tags in ${ctx.timing.interpret}ms.`);
    return { t: 'query_plan', plan };
  },

  build_input: async (inputs, node, _env, ctx) => {
    const { plan } = need(inputs, 'query_plan');
    const datasetId = str(node.data?.datasetId, '') || null;
    const limit = Math.max(0, num(node.data?.maxChunks, 0)); // 0 = no limit
    const facets = Array.isArray(node.data?.activeFacets)
      ? (node.data!.activeFacets as string[])
      : ['topic', 'entities', 'activity', 'temporal', 'evidence'];
    const scopedPlan: QueryPlan = { ...plan, filters: { ...plan.filters, dataset_id: datasetId, limit } };
    const input = buildRetrievalInput(scopedPlan, {
      datasetId,
      limit,
      activeFacets: facets as RetrievalInput['controls']['activeFacets'],
      tagsEnabled: true,
      minWChunk: num(node.data?.weightThreshold, 0),
      minRelevanceToFile: num(node.data?.minRelevanceToFile, 0),
      groundingK: Math.max(0, num(node.data?.groundingK, 0)), // 0 = no cap
      minSim: num(node.data?.minSim, 0.78),
      runId: str(node.data?.runId, 'pilot_full_herb'),
    });
    ctx.plan = scopedPlan;
    ctx.retrievalInput = input;
    return { t: 'retrieval_input', input };
  },

  ground: async (inputs, _node, env, ctx) => {
    const { input } = need(inputs, 'retrieval_input');
    env.log('ground', 'running',
      `Grounding k=${input.controls.groundingK}, min_sim=${input.controls.minSim.toFixed(2)}.`);
    const t0 = Date.now();
    const ground = await groundRetrieval(input, env.neo4jCfg);
    ctx.timing.ground = Date.now() - t0;
    const gs = groundingStats(input.plan.grounding);
    env.log('ground', 'ok',
      `${ground.path} path · ${gs ? `${gs.groundedTags} corpus tags, ${gs.zeroGrounded.length} zero-grounded` : 'no grounding'} (${ctx.timing.ground}ms).`);
    return { t: 'grounded', input, ground };
  },

  // A Query module spliced onto the grounded wire: its composed Cypher becomes
  // the real Lane-A query. Passthrough of the grounded value + the Cypher.
  querymodule: async (inputs, node, env) => {
    const g = need(inputs, 'grounded');
    const composed = composeModuleCypher(
      env.nodes as unknown as Parameters<typeof composeModuleCypher>[0],
      env.edges as unknown as Parameters<typeof composeModuleCypher>[1],
      node.id,
    );
    for (const w of composed.warnings) env.log('querymodule', 'running', w);
    env.log('querymodule', 'ok',
      `Composed query from ${composed.chain.length} fragment(s); it is now Lane A's executed Cypher.`);
    return { ...g, moduleCypher: composed.text };
  },

  retrieve_tags: async (inputs, _node, env, ctx) => {
    // If a Query module is spliced in, its grounded output (carrying
    // moduleCypher) wins over any direct ground→retrieve_tags bypass edge —
    // a wired module always takes effect, never silently ignored.
    const grounded = inputs.filter((i) => i.t === 'grounded') as Extract<Carried, { t: 'grounded' }>[];
    const g = grounded.find((x) => x.moduleCypher) ?? need(inputs, 'grounded');
    const t0 = Date.now();
    const chunks = g.moduleCypher
      ? await runModuleCypher(g.input, env.neo4jCfg, g.ground, g.moduleCypher)
      : await scoreGroundedChunks(g.input, env.neo4jCfg, g.ground);
    ctx.timing.retrieveA = Date.now() - t0;
    env.log('retrieve_tags', 'ok',
      `Lane A: ${chunks.length} chunks (${g.moduleCypher ? 'module Cypher' : 'default query'}, ${ctx.timing.retrieveA}ms).`);
    return { t: 'chunks', branch: 'A', chunks };
  },

  retrieve_baseline: async (inputs, _node, env, ctx) => {
    const { input } = need(inputs, 'retrieval_input');
    const t0 = Date.now();
    const chunks = await retrieveBaseline(input, env.neo4jCfg);
    ctx.timing.retrieveB = Date.now() - t0;
    env.log('retrieve_baseline', 'ok', `Lane B: ${chunks.length} chunks (${ctx.timing.retrieveB}ms).`);
    return { t: 'chunks', branch: 'B', chunks };
  },

  answer: async (inputs, node, env, ctx) => {
    const c = need(inputs, 'chunks');
    if (!ctx.plan) throw new Error('pipeline: answer node ran before interpret produced a plan.');
    const model = str(node.data?.model, env.connConfig.model);
    const t0 = Date.now();
    const ans = await generateAnswer(
      env.prompt, ctx.plan, c.chunks, model, env.connConfig.keys, ctx.mode,
    );
    ctx.timing[c.branch === 'A' ? 'answerA' : 'answerB'] = Date.now() - t0;
    env.log('answer', 'ok', `Lane ${c.branch}: ${ans.tokensOut} output tokens.`);
    return { t: 'answer', branch: c.branch, chunks: c.chunks, response: ans.response, tokensIn: ans.tokensIn, tokensOut: ans.tokensOut };
  },

  compare: async (inputs, _node, _env, ctx) => {
    const A = inputs.find((i) => i.t === 'answer' && i.branch === 'A') as Extract<Carried, { t: 'answer' }> | undefined;
    const B = inputs.find((i) => i.t === 'answer' && i.branch === 'B') as Extract<Carried, { t: 'answer' }> | undefined;
    if (!A || !B) throw new Error(`pipeline: compare needs an A and a B answer (got ${inputs.map((i) => (i.t === 'answer' ? i.branch : i.t)).join(', ') || 'nothing'}).`);
    const plan = ctx.plan;
    const tm = ctx.timing;
    tm.total = Date.now() - ctx.start;
    const metrics = {
      grounding: groundingStats(plan?.grounding),
      retrieval: {
        A: laneChunkStats(A.chunks),
        B: laneChunkStats(B.chunks),
        overlap: chunkSetOverlap(A.chunks, B.chunks),
      },
      citations: {
        A: parseCitations(A.response, A.chunks.length),
        B: parseCitations(B.response, B.chunks.length),
      },
      latency: {
        interpret: tm.interpret ?? null,
        ground: tm.ground ?? null,
        retrieveA: tm.retrieveA ?? null,
        retrieveB: tm.retrieveB ?? null,
        answerA: tm.answerA ?? null,
        answerB: tm.answerB ?? null,
        total: tm.total ?? null,
      },
    };
    const results = {
      lane_A: {
        chunks: A.chunks.length, response: A.response,
        tokensIn: A.tokensIn, tokensOut: A.tokensOut,
        durationMs: (tm.interpret ?? 0) + (tm.ground ?? 0) + (tm.retrieveA ?? 0) + (tm.answerA ?? 0),
        plan, retrievalInput: ctx.retrievalInput, retrievedChunks: A.chunks,
        topFacets: plan
          ? [...new Set(plan.tags.flatMap((t) => Object.entries(t.facets).filter(([, v]) => v >= 0.5).map(([k]) => k)))].slice(0, 4)
          : [],
      },
      lane_B: {
        chunks: B.chunks.length, response: B.response,
        tokensIn: B.tokensIn, tokensOut: B.tokensOut,
        durationMs: (tm.interpret ?? 0) + (tm.retrieveB ?? 0) + (tm.answerB ?? 0),
        plan: null, retrievalInput: ctx.retrievalInput, retrievedChunks: B.chunks, topFacets: [],
      },
      metrics,
    };
    return { t: 'result', results, metrics };
  },

  // Typed passthrough: records what flows through, changes nothing. Safe to
  // splice anywhere a type matches (the user's testing-layer requirement).
  probe: async (inputs, node, env) => {
    const v = inputs[0];
    if (!v) throw new Error('pipeline: probe node has no input.');
    const label = str(node.data?.label, 'probe');
    const summary =
      v.t === 'chunks' ? `${v.chunks.length} chunks (lane ${v.branch})`
        : v.t === 'answer' ? `answer lane ${v.branch}, ${v.tokensOut} tok`
          : v.t === 'query_plan' ? `${v.plan.tags.length} plan tags`
            : v.t;
    env.log(`probe:${label}`, 'ok', `passthrough — ${summary}`);
    return v;
  },
};

export const EXECUTABLE_KINDS = new Set(Object.keys(EXECUTORS));

// ─── Graph runner ───────────────────────────────────────────────────────────
/** The executor kind for a node: a `queryGroup` is the `querymodule` step;
 *  every other participant is a stage carrying `data.kind`. */
function kindOf(node: GraphNode): string | undefined {
  if (node.type === 'queryGroup') return 'querymodule';
  return typeof node.data?.kind === 'string' ? node.data.kind : undefined;
}

function laneExecutableNodes(
  nodes: GraphNode[], edges: GraphEdge[], laneId: string,
): GraphNode[] {
  const stages = nodes.filter(
    (n) => n.parentId === laneId && n.type === 'stage'
      && typeof n.data?.kind === 'string' && EXECUTORS[n.data.kind] && !n.data?.disabled,
  );
  const stageIds = new Set(stages.map((s) => s.id));
  // A Query module participates if it is wired to a lane stage (it need not
  // be parented to the lane — modules are free containers on the canvas).
  const modules = nodes.filter(
    (n) => n.type === 'queryGroup' && !n.data?.disabled
      && edges.some((e) =>
        (e.source === n.id && stageIds.has(e.target)) ||
        (e.target === n.id && stageIds.has(e.source))),
  );
  return [...stages, ...modules];
}

/** Kahn topological order; a cycle is a loud error, never a silent skip. */
function topoOrder(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  const ids = new Set(nodes.map((n) => n.id));
  const internal = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  const outs = new Map<string, string[]>();
  for (const e of internal) {
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
    outs.set(e.source, [...(outs.get(e.source) ?? []), e.target]);
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const queue = nodes
    .filter((n) => (indeg.get(n.id) ?? 0) === 0)
    .sort((a, b) => (a.position?.x ?? 0) - (b.position?.x ?? 0));
  const order: GraphNode[] = [];
  while (queue.length) {
    const n = queue.shift()!;
    order.push(n);
    for (const t of outs.get(n.id) ?? []) {
      indeg.set(t, (indeg.get(t) ?? 0) - 1);
      if ((indeg.get(t) ?? 0) === 0) queue.push(byId.get(t)!);
    }
  }
  if (order.length !== nodes.length) {
    throw new Error('pipeline: the wired nodes contain a cycle — execution order is undefined. Remove the back-edge.');
  }
  return order;
}

export interface RunGraphResult { results: unknown; metrics: unknown }

/**
 * Execute the executable nodes of `laneId` in wired order. Returns the
 * `compare` node's output. Throws loudly if the graph has no terminal
 * `compare`, a cycle, or a contract mismatch — never a silent partial run.
 */
export async function runUsageGraph(
  nodes: GraphNode[], edges: GraphEdge[], laneId: string, env: RunEnv,
): Promise<RunGraphResult> {
  const laneNodes = laneExecutableNodes(nodes, edges, laneId);
  if (!laneNodes.length) {
    throw new Error('pipeline: the Usage lane has no executable nodes wired.');
  }
  const order = topoOrder(laneNodes, edges);
  const laneIds = new Set(laneNodes.map((n) => n.id));
  const inboundOf = (id: string) =>
    edges.filter((e) => e.target === id && laneIds.has(e.source));

  const ctx: RunCtx = { prompt: env.prompt, mode: 'context', plan: null, retrievalInput: null, timing: {}, start: Date.now() };
  const outputs = new Map<string, Carried>();

  for (const node of order) {
    const kind = kindOf(node);
    const exec = kind ? EXECUTORS[kind] : undefined;
    if (!exec) {
      throw new Error(`pipeline: node ${node.id} has no executor (kind ${kind ?? 'unknown'}).`);
    }
    const inputs = inboundOf(node.id)
      .map((e) => outputs.get(e.source))
      .filter((v): v is Carried => !!v);
    let out: Carried;
    try {
      out = await exec(inputs, node, env, ctx);
    } catch (err) {
      env.log(kind ?? 'unknown', 'failed', (err as Error).message);
      throw err;
    }
    outputs.set(node.id, out);
  }

  const result = [...outputs.values()].find((v) => v.t === 'result') as
    | Extract<Carried, { t: 'result' }>
    | undefined;
  if (!result) {
    throw new Error('pipeline: no `compare` node produced a result — wire the A and B answers into a compare node.');
  }
  return { results: result.results, metrics: result.metrics };
}

// ─── Run Builder: a Run is a first-class, comparable config ─────────────────
/**
 * A **Run** is a full snapshot of every lever the canvas spreads across its
 * nodes — collapsed into one object you can build, vary, and stack. The fields
 * map 1:1 to the node that owns the lever in `runUsageGraph` (prompt mode,
 * interpret model/dataset, build_input controls, the route fork, answer
 * model). `runRunSpec` executes ONE route end-to-end by calling the same
 * service functions the executors call — no synthetic canvas, no required
 * `compare` node, so N independent configs run side by side. The A/B
 * `runUsageGraph` path above is untouched.
 */
export type RunRoute = 'tags' | 'baseline' | 'content' | 'module' | 'sql_agent';

export interface RunSpec {
  id: string;
  label: string;
  /** Neo4j database (`herb` vs the pruned `herb-eval`). Was a global. */
  database: string;
  /** Which retrieval executor terminates the path. `content` is the RQ2
   *  conventional Lucene control (no interpret/ground/gate). */
  route: RunRoute;
  /** `queryGroup` node id when `route === 'module'`. */
  moduleId: string | null;
  /** `interpret` node levers. */
  interpret: { model: string; datasetId: string | null };
  /** `build_input` node levers. */
  buildInput: {
    maxChunks: number;
    weightThreshold: number;
    minRelevanceToFile: number;
    groundingK: number;
    minSim: number;
    activeFacets: RetrievalInput['controls']['activeFacets'];
    runId: string;
  };
  /** `prompt`/`answer` node levers. `temperature` feeds both LLM calls. */
  answer: { model: string; mode: AnswerMode };
  temperature: number;
  /** Headless-only levers for `route === 'sql_agent'` (RAGAS export → Python). */
  sqlAgent: {
    maxToolCalls: number;
    maxRowsPerQuery: number;
    maxCellChars: number;
  };
}

export interface RunResult {
  specId: string;
  label: string;
  route: RunRoute;
  database: string;
  response: string;
  chunks: number;
  tokensIn: number;
  tokensOut: number;
  durationMs: number;
  plan: QueryPlan | null;
  retrievalInput: RetrievalInput | null;
  retrievedChunks: RetrievedChunk[];
  topFacets: string[];
  metrics: {
    grounding: ReturnType<typeof groundingStats>;
    retrieval: ReturnType<typeof laneChunkStats>;
    citations: ReturnType<typeof parseCitations>;
    latency: Record<string, number | null>;
  };
}

/** A conventional-baseline plan: `content` retrieval has no interpret step but
 *  the answer LLM still needs an `answer_job`. Mirrors the interpreter default
 *  so the answer prompt is identical to the graph arm — only evidence differs. */
function contentRoutePlan(prompt: string, datasetId: string | null, limit: number): QueryPlan {
  return {
    description: prompt,
    tags: [],
    filters: {
      dataset_id: datasetId, file_ids: [], min_w_chunk: 0, min_relevance_to_file: 0,
      limit, gate: { product: null, section: null, channel: null, employee_id: null, years: [] },
    },
    answer_job: {
      mode: 'direct_answer',
      evidence_policy: 'retrieved_only',
      missing_evidence_policy: 'say_insufficient_evidence',
    },
    warnings: [],
  };
}

/** Execute one Run end-to-end. Loud on every failure path — no degraded run. */
export async function runRunSpec(spec: RunSpec, env: RunEnv): Promise<RunResult> {
  if (spec.route === 'sql_agent') {
    // The SQL-agent baseline runs server-side (Python + SQLite); the browser
    // cannot execute it. Export this spec with "Export RAGAS run" and feed the
    // resulting config to `npm run ragas:export`, which dispatches to
    // backend/baselines/sql_agent.py.
    throw new Error(
      `Run "${spec.label}": the SQL-agent route runs server-side and cannot ` +
      `execute in the browser. Use "Export RAGAS run" on this card and run ` +
      `the gold-set via \`npm run ragas:export -- --config <that.json>\`.`,
    );
  }
  const { prompt, connConfig, log } = env;
  const cfg = { ...env.neo4jCfg, database: spec.database };
  const datasetId = spec.interpret.datasetId || null;
  const limit = Math.max(0, spec.buildInput.maxChunks); // 0 = no limit
  const temp = spec.temperature;
  const tag = `run:${spec.label}`;
  const start = Date.now();
  const timing: Record<string, number | null> = {};
  let t0: number;

  let plan: QueryPlan;
  let input: RetrievalInput | null = null;
  let chunks: RetrievedChunk[];

  if (spec.route === 'content') {
    plan = contentRoutePlan(prompt, datasetId, limit);
    log(tag, 'running', `[${spec.label}] conventional content baseline (no interpret/ground/gate).`);
    t0 = Date.now();
    chunks = await retrieveBaselineContent(prompt, cfg, { limit, datasetId });
    timing.retrieve = Date.now() - t0;
  } else {
    log(tag, 'running', `[${spec.label}] interpret with ${spec.interpret.model}.`);
    t0 = Date.now();
    plan = await interpretPrompt(
      prompt, spec.interpret.model, connConfig.keys, datasetId, temp,
    );
    timing.interpret = Date.now() - t0;
    const scopedPlan: QueryPlan = { ...plan, filters: { ...plan.filters, dataset_id: datasetId, limit } };
    input = buildRetrievalInput(scopedPlan, {
      datasetId,
      limit,
      activeFacets: spec.buildInput.activeFacets,
      tagsEnabled: true,
      minWChunk: spec.buildInput.weightThreshold,
      minRelevanceToFile: spec.buildInput.minRelevanceToFile,
      groundingK: Math.max(0, spec.buildInput.groundingK), // 0 = no cap
      minSim: spec.buildInput.minSim,
      runId: spec.buildInput.runId,
    });
    plan = scopedPlan;

    if (spec.route === 'baseline') {
      t0 = Date.now();
      chunks = await retrieveBaseline(input, cfg);
      timing.retrieve = Date.now() - t0;
    } else {
      t0 = Date.now();
      const ground = await groundRetrieval(input, cfg);
      timing.ground = Date.now() - t0;
      if (spec.route === 'module') {
        if (!spec.moduleId) {
          throw new Error(`run "${spec.label}": route is "module" but no Query module is selected.`);
        }
        const composed = composeModuleCypher(
          env.nodes as unknown as Parameters<typeof composeModuleCypher>[0],
          env.edges as unknown as Parameters<typeof composeModuleCypher>[1],
          spec.moduleId,
        );
        for (const w of composed.warnings) log(tag, 'running', `[${spec.label}] ${w}`);
        t0 = Date.now();
        chunks = await runModuleCypher(input, cfg, ground, composed.text);
        timing.retrieve = Date.now() - t0;
      } else {
        t0 = Date.now();
        chunks = await scoreGroundedChunks(input, cfg, ground);
        timing.retrieve = Date.now() - t0;
      }
    }
  }
  log(tag, 'running', `[${spec.label}] ${chunks.length} chunks via ${spec.route}; answering with ${spec.answer.model}.`);

  t0 = Date.now();
  const ans = await generateAnswer(
    prompt, plan, chunks, spec.answer.model, connConfig.keys, spec.answer.mode, temp,
  );
  timing.answer = Date.now() - t0;
  timing.total = Date.now() - start;
  log(tag, 'ok', `[${spec.label}] done — ${chunks.length} chunks, ${ans.tokensOut} out tok (${timing.total}ms).`);

  return {
    specId: spec.id,
    label: spec.label,
    route: spec.route,
    database: spec.database,
    response: ans.response,
    chunks: chunks.length,
    tokensIn: ans.tokensIn,
    tokensOut: ans.tokensOut,
    durationMs: timing.total ?? 0,
    plan: spec.route === 'content' ? null : plan,
    retrievalInput: input,
    retrievedChunks: chunks,
    topFacets: spec.route === 'content' || !plan
      ? []
      : [...new Set(plan.tags.flatMap((t) =>
          Object.entries(t.facets).filter(([, v]) => v >= 0.5).map(([k]) => k)))].slice(0, 4),
    metrics: {
      grounding: groundingStats(plan?.grounding),
      retrieval: laneChunkStats(chunks),
      citations: parseCitations(ans.response, chunks.length),
      latency: timing,
    },
  };
}

/** Pairwise chunk-set overlap across N runs (generalizes `chunkSetOverlap`). */
export function compareRuns(results: RunResult[]) {
  const pairs: { a: string; b: string; count: number; jaccard: number }[] = [];
  for (let i = 0; i < results.length; i++) {
    for (let j = i + 1; j < results.length; j++) {
      const o = chunkSetOverlap(results[i].retrievedChunks, results[j].retrievedChunks);
      pairs.push({ a: results[i].label, b: results[j].label, ...o });
    }
  }
  return { pairs };
}
