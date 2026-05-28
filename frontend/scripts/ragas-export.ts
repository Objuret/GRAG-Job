/**
 * Headless RAGAS export harness.
 *
 *   npm --workspace frontend run ragas:export -- --questions <file> --out <file>
 *
 * Drives the same service path as the current Usage graph:
 * interpretPrompt -> buildRetrievalInput -> groundRetrieval ->
 * scoreGroundedChunks -> generateAnswer, against the live eval-safe Neo4j
 * graph and Anthropic. For each question it writes one JSONL
 * row with the fields RAGAS needs:
 *
 *   user_input         = the question
 *   retrieved_contexts = eval evidence (same slice as the answer LLM)
 *   response           = the answer the pipeline actually generated
 *
 * plus a `meta` block (plan, grounding, gate, tokens, timing, error) for
 * debugging. Full retrieval audit: meta.n_chunks_retrieved, meta.chunk_ids_retrieved,
 * meta.retrieved_chunks (rank/id/score for the eval slice).
 *
 * Config resolution per key: process.env[KEY] -> process.env[VITE_KEY] ->
 * .env files (frontend/.env.local, frontend/.env, repo .env) -> default.
 * Mirrors the app's Vite env so an existing frontend/.env.local just works.
 *
 * The e5 grounding model runs from disk, not the browser web root: the
 * harness repoints transformers.js `localModelPath` at frontend/public/models
 * and fails loud if the assembled onnx is missing (run `npm install` /
 * `npm run assets:assemble`). No remote HF fetch, matching embeddings.ts.
 */
import { readFileSync, existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { env as hfEnv } from '@xenova/transformers';

import { interpretPrompt, type QueryPlan } from '../src/services/interpreter';
import {
  buildRetrievalInput,
  groundRetrieval,
  retrieveBaselineContent,
  scoreGroundedChunks,
  type RetrievedChunk,
} from '../src/services/retrieval';
import { generateAnswer, selectEvidenceChunks, type AnswerMode } from '../src/services/answer';
import type { Neo4jConfig } from '../src/services/neo4j';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, '..');
const REPO_ROOT = resolve(FRONTEND_ROOT, '..');

// --- .env loading (no dependency; never logs values) -----------------------

function parseEnvFile(path: string): Record<string, string> {
  const out: Record<string, string> = {};
  if (!existsSync(path)) return out;
  for (const rawLine of readFileSync(path, 'utf-8').split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (key) out[key] = val;
  }
  return out;
}

const fileEnv: Record<string, string> = {
  ...parseEnvFile(join(REPO_ROOT, '.env')),
  ...parseEnvFile(join(FRONTEND_ROOT, '.env')),
  ...parseEnvFile(join(FRONTEND_ROOT, '.env.local')),
};

function cfg(name: string, dflt = ''): string {
  return (
    process.env[name] ??
    process.env[`VITE_${name}`] ??
    fileEnv[name] ??
    fileEnv[`VITE_${name}`] ??
    dflt
  );
}

// --- CLI args --------------------------------------------------------------

function arg(flag: string, dflt?: string): string | undefined {
  const i = process.argv.indexOf(flag);
  if (i !== -1 && i + 1 < process.argv.length) return process.argv[i + 1];
  return dflt;
}
const hasFlag = (flag: string) => process.argv.includes(flag);

// `npm --workspace frontend run` sets cwd to frontend/, so a repo-root-relative
// path like `frontend/scripts/x.jsonl` would double to frontend/frontend/...
// Resolve --questions against several bases and take the first that exists;
// --out is treated as repo-root-relative (resolve() passes absolutes through).
function resolveExisting(p: string, bases: string[]): string {
  for (const b of bases) {
    const cand = resolve(b, p);
    if (existsSync(cand)) return cand;
  }
  return resolve(process.cwd(), p); // keep a sensible path for the not-found error
}

const questionsArg = arg('--questions');
const questionsPath = questionsArg
  ? resolveExisting(questionsArg, [process.cwd(), REPO_ROOT, FRONTEND_ROOT, SCRIPT_DIR])
  : join(SCRIPT_DIR, 'ragas-questions.example.jsonl');

const outArg = arg('--out');
const outPath = outArg
  ? resolve(REPO_ROOT, outArg)
  : join(REPO_ROOT, 'ragas_exports', 'ragas_samples.jsonl');
const maxQuestions = Number(arg('--max', '0')) || 0; // 0 = all
const dryRun = hasFlag('--dry-run'); // interpret+retrieve only, skip the answer LLM
const fresh = hasFlag('--fresh');    // truncate the out file; default resumes
const retryErrors = hasFlag('--retry-errors'); // re-run rows with meta.error only

// Optional RunSpec-derived config from the workbench's "Export RAGAS run"
// button (see specToRagasConfig in frontend/src/App.jsx). CLI flags still win;
// this object only provides defaults.
interface RunCfg {
  $schema?: string; label?: string; route_origin?: string;
  mode?: 'graph' | 'baseline' | 'sql_agent';
  database?: string;
  model?: string; interpreter_model?: string;
  prompt_mode?: string;
  dataset_id?: string | null;
  temperature?: number;
  limit?: number;
  grounding_k?: number;
  min_sim?: number;
  min_w_chunk?: number;
  min_relevance_to_file?: number;
  active_facets?: string[];
  exclude_sections?: string[];
  max_tool_calls?: number;
  max_rows_per_query?: number;
  max_cell_chars?: number;
  concurrency?: number;
  answer_max_chunks?: number;
  link_only_scoring?: boolean;
}
const configArg = arg('--config');
let runCfg: RunCfg = {};
if (configArg) {
  const p = resolveExisting(configArg, [process.cwd(), REPO_ROOT, FRONTEND_ROOT, SCRIPT_DIR]);
  if (!existsSync(p)) throw new Error(`--config file not found: ${p}`);
  let parsed: unknown;
  try { parsed = JSON.parse(readFileSync(p, 'utf-8')); }
  catch (e) { throw new Error(`--config file is not valid JSON (${p}): ${(e as Error).message}`); }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`--config file does not contain a JSON object: ${p}`);
  }
  runCfg = parsed as RunCfg;
  if (runCfg.mode !== 'graph' && runCfg.mode !== 'baseline' && runCfg.mode !== 'sql_agent') {
    throw new Error(
      `--config "${p}" has invalid mode=${JSON.stringify(runCfg.mode)}. ` +
      `Supported: 'graph', 'baseline', 'sql_agent' (RunSpec route='module' has no batch path).`,
    );
  }
  console.log(`Loaded RunSpec config: "${runCfg.label ?? '(no label)'}" from ${p}`);
}

// Precedence per setting: explicit CLI flag > config file > env/.env > hard default.
function pickStr(flag: string | null, cfgVal: string | null | undefined, envName: string | null, dflt: string): string {
  if (flag) { const cli = arg(flag); if (cli !== undefined) return cli; }
  if (cfgVal != null && cfgVal !== '') return String(cfgVal);
  if (envName) return cfg(envName, dflt);
  return dflt;
}
function pickNum(flag: string | null, cfgVal: number | undefined, envName: string | null, dflt: number): number {
  if (flag) { const cli = arg(flag); if (cli !== undefined) { const n = Number(cli); return Number.isFinite(n) ? n : dflt; } }
  if (cfgVal != null && Number.isFinite(cfgVal)) return cfgVal;
  if (envName) { const n = Number(cfg(envName, String(dflt))); return Number.isFinite(n) ? n : dflt; }
  return dflt;
}

const model = pickStr('--model', runCfg.model, 'MODEL', 'claude-haiku-4-5');
const interpreterModelRaw = pickStr('--interpreter-model', runCfg.interpreter_model, 'INTERPRETER_MODEL', '');
const interpreterModel = interpreterModelRaw || model;
const promptMode = pickStr('--prompt-mode', runCfg.prompt_mode, 'PROMPT_MODE', 'context') as AnswerMode;
const datasetIdRaw = pickStr('--dataset', runCfg.dataset_id ?? '', 'DATASET_ID', 'Salesforce__HERB');
const datasetId = datasetIdRaw || null;
const retrievalLimit = pickNum('--limit', runCfg.limit, 'RETRIEVAL_LIMIT', 0);
const linkOnlyScoring = hasFlag('--link-only') || runCfg.link_only_scoring === true;
const groundingKDefault = linkOnlyScoring ? 40 : 0;
const groundingK = pickNum('--grounding-k', runCfg.grounding_k, 'GROUNDING_K', groundingKDefault);
const minSim = pickNum(null, runCfg.min_sim, 'MIN_SIM', 0.78);
const minWChunk = pickNum(null, runCfg.min_w_chunk, null, 0);
const minRelevanceToFile = pickNum(null, runCfg.min_relevance_to_file, null, 0);
const sqlMaxToolCalls = pickNum('--max-tool-calls', runCfg.max_tool_calls, 'SQL_MAX_TOOL_CALLS', 0);
const sqlMaxRowsPerQuery = pickNum('--max-rows-per-query', runCfg.max_rows_per_query, 'SQL_MAX_ROWS_PER_QUERY', 0);
const sqlMaxCellChars = pickNum('--max-cell-chars', runCfg.max_cell_chars, 'SQL_MAX_CELL_CHARS', 0);
// Eval-only: drop these chunk sections from retrieval. For the reference run
// pass `--exclude-sections answerable_questions,unanswerable_questions` so the
// pipeline cannot retrieve the gold-answer record into its own evaluation.
const DEFAULT_EXCLUDED_SECTIONS = 'answerable_questions,unanswerable_questions,product_profile';
const excludeSectionsRaw =
  arg('--exclude-sections') ??
  (Array.isArray(runCfg.exclude_sections) ? runCfg.exclude_sections.join(',') : undefined) ??
  cfg('EXCLUDE_SECTIONS', DEFAULT_EXCLUDED_SECTIONS);
const excludeSections = excludeSectionsRaw.split(',').map((s) => s.trim()).filter(Boolean);
// activeFacets has no CLI flag. Config key absent → pipeline default (all five).
// Explicit [] → none (matches browser Run Builder with all facets off).
const activeFacetsFromCfg = Array.isArray(runCfg.active_facets) ? runCfg.active_facets : undefined;
const activeFacetsLabel =
  activeFacetsFromCfg === undefined
    ? '(default all)'
    : activeFacetsFromCfg.length
      ? activeFacetsFromCfg.join(',')
      : '(none)';
// Database normally comes from env (NEO4J_DATABASE) — the config file can
// override that default.
const databaseOverride = runCfg.database || null;

// RQ2 control arm. graph = full transformation-layer pipeline (interpret ->
// ground -> retrieve). baseline = conventional keyword retrieval over raw
// c.content only, no interpret/grounding/enrichment. Same questions, prompt,
// model, answer step, section-exclusion — only the retrieved context differs.
const modeRaw = arg('--mode') ?? runCfg.mode ?? 'graph';
const mode = (modeRaw === 'baseline' ? 'baseline'
            : modeRaw === 'sql_agent' ? 'sql_agent'
            : 'graph') as 'graph' | 'baseline' | 'sql_agent';
/** HERB Lucene baseline returns ~5k hits at limit=0 and breaks the answer API. Graph stays uncapped. */
const BASELINE_EXPORT_DEFAULT_LIMIT = 150;
const baselineRetrievalLimit =
  retrievalLimit > 0 ? retrievalLimit : BASELINE_EXPORT_DEFAULT_LIMIT;
const concurrency = Math.max(
  1,
  Number(arg('--concurrency') ?? runCfg.concurrency ?? cfg('RAGAS_CONCURRENCY', '8')) || 8,
);
/** Answer API + RAGAS eval share one evidence budget (see selectEvidenceChunks). */
const ANSWER_EXPORT_DEFAULT_MAX_CHUNKS = 200;
const answerMaxChunksRaw = Number(
  arg('--answer-max-chunks') ??
    runCfg.answer_max_chunks ??
    cfg('ANSWER_MAX_CHUNKS', String(ANSWER_EXPORT_DEFAULT_MAX_CHUNKS)),
);
const answerMaxChunks =
  Number.isFinite(answerMaxChunksRaw) && answerMaxChunksRaw >= 0
    ? answerMaxChunksRaw
    : ANSWER_EXPORT_DEFAULT_MAX_CHUNKS;
const skipRetryIds = new Set(
  (arg('--skip-ids') ?? 'gold_personalizeforce_34').split(',').map((s) => s.trim()).filter(Boolean),
);
// Thesis 5.7: temperature 0 + repeated runs (median/IQR computed at analysis).
const temperature = pickNum('--temperature', runCfg.temperature, null, 0);
const repeats = Math.max(1, Number(arg('--repeats', '1')) || 1);

// Mirrors interpreter.ts DEFAULT_ANSWER_JOB so the baseline answer prompt is
// byte-identical to the graph arm's (only the evidence differs).
const BASELINE_PLAN = (q: string): QueryPlan => ({
  description: q,
  tags: [],
  filters: {
    dataset_id: datasetId, file_ids: [], min_w_chunk: 0, min_relevance_to_file: 0,
    limit: baselineRetrievalLimit,
    gate: { product: null, section: null, channel: null, employee_id: null, years: [] },
  },
  answer_job: {
    mode: 'direct_answer',
    evidence_policy: 'retrieved_only',
    missing_evidence_policy: 'say_insufficient_evidence',
  },
  warnings: [],
});

const neo4jCfg: Neo4jConfig = {
  uri: cfg('NEO4J_URI', 'bolt://localhost:7687'),
  user: cfg('NEO4J_USER', 'neo4j'),
  password: cfg('NEO4J_PASSWORD', ''),
  // Thesis eval should use the physically pruned graph; allow override via
  // env or the loaded RunSpec config file.
  database: databaseOverride || cfg('NEO4J_DATABASE', 'herb-eval'),
};
// All provider keys; llm.chat() picks the right one based on the model id.
// Adding a provider here = one extra cfg() line + an entry in MODELS.
const keys = {
  anthropic: cfg('ANTHROPIC_API_KEY', ''),
  openai:    cfg('OPENAI_API_KEY', ''),
  deepseek:  cfg('DEEPSEEK_API_KEY', ''),
  ollama:    cfg('OLLAMA_API_KEY', ''),
  groq:      cfg('GROQ_API_KEY', ''),
};

// --- e5 grounding model: load from disk, not the browser web root ----------

const modelsDir = join(FRONTEND_ROOT, 'public', 'models');
const onnxFile = join(modelsDir, 'Xenova', 'e5-small-v2', 'onnx', 'model.onnx');

function preflightModel(): void {
  if (existsSync(onnxFile) && statSync(onnxFile).size > 0) return;
  const partsExist = existsSync(onnxFile + '.part00');
  throw new Error(
    `e5 grounding model not assembled at ${onnxFile}. ` +
      (partsExist
        ? 'The split parts are present — run `npm install` (postinstall assembles it) ' +
          'or `npm run assets:assemble` from the repo root, then re-run.'
        : 'Model files are missing entirely from frontend/public/models/Xenova/e5-small-v2/.'),
  );
}

// embeddings.ts set localModelPath='/models' (Vite web root) at import time;
// repoint the shared transformers.js env at the on-disk dir before any embed.
hfEnv.allowRemoteModels = false;
hfEnv.allowLocalModels = true;
hfEnv.localModelPath = modelsDir;

// --- questions -------------------------------------------------------------

interface QItem {
  id: string;
  question: string;
  /** Optional gold answer (HERB ground_truth) for reference-based metrics. */
  reference?: string;
}

function loadQuestions(path: string): QItem[] {
  if (!existsSync(path)) {
    throw new Error(`Questions file not found: ${path}`);
  }
  const text = readFileSync(path, 'utf-8');
  const items: QItem[] = [];
  if (path.endsWith('.json')) {
    const parsed = JSON.parse(text);
    const arr = Array.isArray(parsed) ? parsed : parsed.questions ?? [];
    arr.forEach((q: unknown, i: number) => {
      if (typeof q === 'string') items.push({ id: `q${i + 1}`, question: q });
      else if (q && typeof q === 'object') {
        const o = q as Record<string, unknown>;
        const ref = o.reference ?? o.ground_truth;
        items.push({
          id: String(o.id ?? `q${i + 1}`),
          question: String(o.question ?? ''),
          ...(ref != null ? { reference: String(ref) } : {}),
        });
      }
    });
  } else {
    // .jsonl OR plain text — try JSON per line, fall back to raw line.
    let n = 0;
    for (const raw of text.split('\n')) {
      const line = raw.trim();
      if (!line || line.startsWith('#')) continue;
      n++;
      let question = line;
      let id = `q${n}`;
      let reference: string | undefined;
      if (line.startsWith('{')) {
        try {
          const o = JSON.parse(line) as Record<string, unknown>;
          question = String(o.question ?? o.user_input ?? '');
          id = String(o.id ?? `q${n}`);
          const ref = o.reference ?? o.ground_truth;
          if (ref != null) reference = String(ref);
        } catch {
          /* not JSON — treat the whole line as the question */
        }
      }
      if (question) items.push({ id, question, ...(reference != null ? { reference } : {}) });
    }
  }
  return items;
}

type ExportRow = {
  id: string;
  question: string;
  user_input: string;
  retrieved_contexts: string[];
  response: string;
  answer: string;
  reference: string | null;
  meta: Record<string, unknown>;
};

function rowSucceeded(r: ExportRow): boolean {
  return !(r.meta?.error) && Boolean((r.response || '').trim());
}

function loadRowsById(path: string): Map<string, ExportRow> {
  const byId = new Map<string, ExportRow>();
  if (!existsSync(path)) return byId;
  for (const raw of readFileSync(path, 'utf-8').split('\n')) {
    const s = raw.trim();
    if (!s) continue;
    try {
      const r = JSON.parse(s) as ExportRow;
      const id = String(r.id);
      const prev = byId.get(id);
      if (!prev || (rowSucceeded(r) && !rowSucceeded(prev)) || (!rowSucceeded(prev) && !rowSucceeded(r))) {
        byId.set(id, r);
      }
    } catch { /* skip bad line */ }
  }
  return byId;
}

function writeRowsById(path: string, byId: Map<string, ExportRow>): void {
  const lines = [...byId.values()].map((r) => JSON.stringify(r));
  writeFileSync(path, lines.length ? `${lines.join('\n')}\n` : '', 'utf-8');
}

// --- main ------------------------------------------------------------------

/**
 * SQL-agent dispatch: hand off to `python -m backend.baselines.sql_agent`.
 *
 * The Python script owns the SQLite store, the tool-use loop, and JSONL
 * emission. We just resolve which provider + base URL + key env var the
 * chosen `model` needs (via the same registry the UI uses) and pass them
 * through, so the model selection in the Run Builder card transfers cleanly
 * to the headless run.
 */
async function runSqlAgent(): Promise<void> {
  const { spawnSync } = await import('node:child_process');
  const { providerOf, PROVIDERS } = await import('../src/data/models.js');

  let provider;
  try { provider = providerOf(model); }
  catch (e) { throw new Error(`SQL agent: ${(e as Error).message}`); }
  if (provider === 'anthropic') {
    throw new Error(
      `SQL agent does not support Anthropic models yet (Anthropic tool-use has a ` +
      `different API shape). Pick a DeepSeek / OpenAI / Ollama Cloud / Groq model.`,
    );
  }
  const baseURL = PROVIDERS[provider].baseURL;
  if (!baseURL) throw new Error(`SQL agent: provider ${provider} has no baseURL configured.`);
  const apiKey = keys[provider as keyof typeof keys];
  if (!apiKey) {
    throw new Error(`SQL agent: ${PROVIDERS[provider].label} key not set (${PROVIDERS[provider].envKeyVar.replace('VITE_', '')}).`);
  }

  mkdirSync(dirname(outPath), { recursive: true });
  const apiKeyEnv = 'SQL_AGENT_API_KEY'; // single env var name regardless of provider
  const args = [
    '-m', 'backend.baselines.sql_agent',
    '--gold-set', questionsPath,
    '--out', outPath,
    '--model', model,
    '--base-url', baseURL,
    '--api-key-env', apiKeyEnv,
  ];
  if (maxQuestions > 0) args.push('--limit', String(maxQuestions));
  args.push('--temperature', String(temperature));
  args.push('--max-tool-calls', String(sqlMaxToolCalls));
  args.push('--max-rows-per-query', String(sqlMaxRowsPerQuery));
  args.push('--max-cell-chars', String(sqlMaxCellChars));

  console.log(
    `RAGAS export (SQL agent)\n` +
    `  questions : ${questionsPath}\n` +
    `  out       : ${outPath}\n` +
    `  model     : ${model}  (provider=${provider}, base=${baseURL})\n` +
    `  caps      : tool_calls=${sqlMaxToolCalls} rows/query=${sqlMaxRowsPerQuery} cell_chars=${sqlMaxCellChars}\n` +
    `  cmd       : python ${args.join(' ')}\n`,
  );

  const res = spawnSync('python', args, {
    cwd: REPO_ROOT,
    env: { ...process.env, [apiKeyEnv]: apiKey },
    stdio: 'inherit',
  });
  if (res.error) throw res.error;
  if (res.status !== 0) {
    throw new Error(`SQL agent script exited with status ${res.status}.`);
  }
}

async function main(): Promise<void> {
  // SQL-agent mode is dispatched to the Python backend script — it doesn't
  // use Neo4j, transformers, or any of the TS pipeline. Short-circuit before
  // those prechecks/preflights run.
  if (mode === 'sql_agent') {
    return runSqlAgent();
  }
  // Key precheck via the same registry the UI uses, so unknown models / missing
  // keys fail before any network calls. Loud on unknown model id.
  {
    const { providerOf, PROVIDERS } = await import('../src/data/models.js');
    const usedModels = [interpreterModel, model];
    const missing: string[] = [];
    const seen = new Set<string>();
    for (const m of usedModels) {
      let prov;
      try { prov = providerOf(m); } catch (e) { missing.push((e as Error).message); continue; }
      if (seen.has(prov)) continue;
      seen.add(prov);
      if (!keys[prov as keyof typeof keys]) {
        missing.push(`${PROVIDERS[prov].label} (${PROVIDERS[prov].envKeyVar.replace('VITE_', '')})`);
      }
    }
    if (missing.length) throw new Error(`API key/model error: ${missing.join('; ')}.`);
  }
  if (!neo4jCfg.password) {
    throw new Error('NEO4J_PASSWORD (or VITE_NEO4J_PASSWORD) is not set.');
  }
  if (mode === 'graph') preflightModel();

  mkdirSync(join(REPO_ROOT, 'ragas_exports'), { recursive: true });

  const questions = loadQuestions(questionsPath);
  const slice = maxQuestions > 0 ? questions.slice(0, maxQuestions) : questions;
  if (!slice.length) throw new Error(`No questions loaded from ${questionsPath}`);

  mkdirSync(dirname(outPath), { recursive: true });

  console.log(
    `RAGAS export\n` +
      `  arm       : ${mode}  (repeats=${repeats}, temperature=${temperature})\n` +
      `  questions : ${slice.length} from ${questionsPath}\n` +
      `  out       : ${outPath}\n` +
      `  graph     : ${neo4jCfg.uri} db=${neo4jCfg.database} dataset=${datasetId}\n` +
      `  model     : answer=${model} interpret=${mode === 'baseline' ? '(skipped)' : interpreterModel} promptMode=${promptMode}\n` +
      `  retrieval : ${mode === 'baseline'
        ? `content-only full-text (no tags/grounding/gate), limit=${baselineRetrievalLimit}` +
          (retrievalLimit <= 0 ? ` (baseline default; graph unchanged at limit=0)` : '')
        : `limit=${retrievalLimit} groundingK=${groundingK} minSim=${minSim}` +
          ` linkOnly=${linkOnlyScoring}` +
          ` minWChunk=${minWChunk} minRelToFile=${minRelevanceToFile}` +
          ` facets=${activeFacetsLabel}`}\n` +
      `  exclude   : ${excludeSections.length ? excludeSections.join(',') : '(none)'}` +
      `${configArg ? `\n  config    : ${runCfg.label ?? '(no label)'} (${configArg})` : ''}` +
      `\n  parallel  : concurrency=${concurrency}` +
      `\n  evidence  : max_chunks=${answerMaxChunks} (retrieved_contexts = answer slice; full ids in meta)` +
      `${retryErrors ? `\n  retry     : errors only, skip=${[...skipRetryIds].join(',')}` : ''}` +
      `${dryRun ? '\n  DRY RUN — answer LLM skipped' : ''}\n`,
  );

  const rowStore: Map<string, ExportRow> = fresh ? new Map() : loadRowsById(outPath);
  const doneIds = new Set<string>();
  for (const [id, r] of rowStore) {
    if (retryErrors) {
      if (rowSucceeded(r)) doneIds.add(id);
    } else {
      doneIds.add(id);
    }
  }
  for (const id of skipRetryIds) doneIds.add(id);

  let flushLock = Promise.resolve();
  const flushRows = () => {
    flushLock = flushLock.then(() => { writeRowsById(outPath, rowStore); });
    return flushLock;
  };
  if (fresh) writeFileSync(outPath, '', 'utf-8');

  let ok = 0;
  let errored = 0;
  let resumed = 0;

  const totalUnits = slice.length * repeats;
  type WorkItem = {
    unit: number;
    rowId: string;
    question: string;
    reference?: string;
    rep: number;
  };
  const pending: WorkItem[] = [];
  let unit = 0;
  for (let i = 0; i < slice.length; i++) {
    const { id, question, reference } = slice[i];
    for (let rep = 1; rep <= repeats; rep++) {
      unit++;
      const rowId = repeats > 1 ? `${id}#r${rep}` : id;
      if (doneIds.has(rowId)) {
        resumed++;
        console.log(`  [${unit}/${totalUnits}] ${rowId} … skip (already ok)`);
        continue;
      }
      if (skipRetryIds.has(rowId)) {
        resumed++;
        console.log(`  [${unit}/${totalUnits}] ${rowId} … skip (permanent eval failure)`);
        continue;
      }
      pending.push({ unit, rowId, question, reference, rep });
    }
  }

  let writeLock = Promise.resolve();
  const appendRow = (line: string) => {
    writeLock = writeLock.then(() => { appendFileSync(outPath, line, 'utf-8'); });
    return writeLock;
  };

  async function processOne(work: WorkItem): Promise<void> {
    const { unit: u, rowId, question, reference, rep } = work;
    const t0 = Date.now();
    const meta: Record<string, unknown> = {
      mode,
      repeat: rep,
      model,
      interpreter_model: interpreterModel,
      prompt_mode: promptMode,
      temperature,
      dataset_id: datasetId,
      database: neo4jCfg.database,
      exclude_sections: excludeSections,
    };
    let contexts: string[] = [];
    let response = '';
    let logSuffix: string;

    try {
      let chunks: RetrievedChunk[];
      let planForAnswer: QueryPlan;

      if (mode === 'baseline') {
        planForAnswer = BASELINE_PLAN(question);
        chunks = await retrieveBaselineContent(question, neo4jCfg, {
          limit: baselineRetrievalLimit,
          datasetId,
          excludedSections: excludeSections,
        });
        meta.warnings = [];
      } else {
        const plan = await interpretPrompt(
          question, interpreterModel, keys, datasetId, temperature,
        );
        planForAnswer = {
          ...plan,
          filters: {
            ...plan.filters,
            dataset_id: datasetId,
            limit: retrievalLimit,
            min_w_chunk: minWChunk,
            min_relevance_to_file: minRelevanceToFile,
          },
        };
        const input = buildRetrievalInput(planForAnswer, {
          limit: retrievalLimit,
          datasetId,
          groundingK,
          minSim,
          minWChunk,
          minRelevanceToFile,
          linkOnlyScoring,
          ...(activeFacetsFromCfg !== undefined ? { activeFacets: activeFacetsFromCfg as never } : {}),
          tagsEnabled: true,
          excludedSections: excludeSections,
        });
        const ground = await groundRetrieval(input, neo4jCfg);
        chunks = await scoreGroundedChunks(input, neo4jCfg, ground);
        meta.retrieval_input = {
          scope: input.scope,
          controls: input.controls,
          gate: input.gate,
          link_only_scoring: linkOnlyScoring,
        };
        meta.ground_path = ground.path;
        meta.plan_description = planForAnswer.description;
        meta.warnings = planForAnswer.warnings;
        meta.gate = planForAnswer.filters.gate;
        meta.grounding = planForAnswer.grounding ?? [];
      }

      contexts = chunks.map((c) => c.content).filter(Boolean);
      const evidenceOpts = {
        maxAnswerChunks: answerMaxChunks,
        maxChunkChars: 1800,
        scrubForApi: true,
      };
      const evalChunks = selectEvidenceChunks(chunks, evidenceOpts);
      const evalContexts = evalChunks.map((c) => c.content).filter(Boolean);
      meta.n_chunks_retrieved = chunks.length;
      meta.chunk_ids_retrieved = chunks.map((c) => c.chunkId);
      meta.n_chunks_eval = evalChunks.length;
      meta.chunk_ids = evalChunks.map((c) => c.chunkId);
      meta.retrieved_chunks = evalChunks.map((c, i) => ({
        rank: i + 1,
        chunk_id: c.chunkId,
        file_id: c.fileId,
        score: c.score,
      }));
      meta.file_ids = [...new Set(evalChunks.map((c) => c.fileId))];
      meta.answer_max_chunks = answerMaxChunks;
      meta.answer_scrubbed = true;
      meta.evidence_max_chars = 1800;

      if (!dryRun) {
        const ans = await generateAnswer(
          question, planForAnswer, chunks, model, keys, promptMode, temperature,
          evidenceOpts,
        );
        response = ans.response;
        meta.tokens = { answer_in: ans.tokensIn, answer_out: ans.tokensOut };
        meta.answer_chunks = evalChunks.length;
      }
      contexts = evalContexts;
      meta.elapsed_ms = Date.now() - t0;
      meta.error = null;
      ok++;
      logSuffix = `ok (${meta.n_chunks_retrieved} retrieved, ${evalContexts.length} eval${dryRun ? '' : `, ${response.length} chars`})`;
    } catch (err) {
      meta.elapsed_ms = Date.now() - t0;
      meta.error = err instanceof Error ? err.message : String(err);
      errored++;
      logSuffix = `ERROR: ${meta.error}`;
    }

    rowStore.set(rowId, {
      id: rowId,
      question,
      user_input: question,
      retrieved_contexts: contexts,
      response,
      answer: response,
      reference: reference ?? null,
      meta,
    });
    await flushRows();
    console.log(`  [${u}/${totalUnits}] ${rowId} (${mode}) … ${logSuffix}`);
  }

  let next = 0;
  async function worker(): Promise<void> {
    while (true) {
      const idx = next++;
      if (idx >= pending.length) return;
      await processOne(pending[idx]);
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, pending.length) }, () => worker()),
  );
  await flushLock;

  console.log(
    `\nDone. ${ok} ok, ${errored} errored, ${resumed} pre-existing, ${totalUnits} total (${mode}).\n` +
      `Wrote ${outPath}` +
      (ok + resumed < totalUnits
        ? `\nIncomplete — re-run the same command to resume the remaining ${totalUnits - ok - resumed}.`
        : ''),
  );
  if (errored > 0) process.exitCode = 1;
}

main().catch((err) => {
  console.error(`\nFATAL: ${err instanceof Error ? err.message : String(err)}`);
  process.exit(2);
});
