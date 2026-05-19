/**
 * Headless RAGAS export harness.
 *
 *   npm --workspace frontend run ragas:export -- --questions <file> --out <file>
 *
 * Drives the SAME browser pipeline the app runs (App.jsx:runPipeline, main
 * lane only): interpretPrompt -> retrieveChunks -> generateAnswer, against the
 * live `herb` Neo4j graph and Anthropic. For each question it writes one JSONL
 * row with the fields RAGAS needs reference-free:
 *
 *   user_input         = the question
 *   retrieved_contexts = the chunk contents retrieval actually returned
 *   response           = the answer the pipeline actually generated
 *
 * plus a `meta` block (plan, grounding, gate, tokens, timing, error) for
 * debugging and later reference-based metrics. This is the producer half; the
 * Python RAGAS runner consumes the JSONL and is intentionally decoupled.
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
import { readFileSync, existsSync, mkdirSync, writeFileSync, appendFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { env as hfEnv } from '@xenova/transformers';

import { interpretPrompt, type QueryPlan } from '../src/services/interpreter';
import { retrieveChunks, retrieveBaselineContent, type RetrievedChunk } from '../src/services/retrieval';
import { generateAnswer, type AnswerMode } from '../src/services/answer';
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
  : join(REPO_ROOT, 'backend', 'evaluation', 'ragas_samples.jsonl');
const maxQuestions = Number(arg('--max', '0')) || 0; // 0 = all
const dryRun = hasFlag('--dry-run'); // interpret+retrieve only, skip the answer LLM
const fresh = hasFlag('--fresh');    // truncate the out file; default resumes

const model = arg('--model', cfg('MODEL', 'claude-haiku-4-5'))!;
const interpreterModel = arg('--interpreter-model', cfg('INTERPRETER_MODEL', '')) || model;
const promptMode = (arg('--prompt-mode', cfg('PROMPT_MODE', 'context')) as AnswerMode);
const datasetId = arg('--dataset', cfg('DATASET_ID', 'Salesforce__HERB')) || null;
const retrievalLimit = Number(arg('--limit', cfg('RETRIEVAL_LIMIT', '20'))) || 20;
const groundingK = Number(cfg('GROUNDING_K', '10')) || 10;
const minSim = Number(cfg('MIN_SIM', '0')) || 0;
// Eval-only: drop these chunk sections from retrieval. For the reference run
// pass `--exclude-sections answerable_questions,unanswerable_questions` so the
// pipeline cannot retrieve the gold-answer record into its own evaluation.
const excludeSections = (arg('--exclude-sections', cfg('EXCLUDE_SECTIONS', '')) || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

// RQ2 control arm. graph = full transformation-layer pipeline (interpret ->
// ground -> retrieve). baseline = conventional keyword retrieval over raw
// c.content only, no interpret/grounding/enrichment. Same questions, prompt,
// model, answer step, section-exclusion — only the retrieved context differs.
const mode = (arg('--mode', 'graph') === 'baseline' ? 'baseline' : 'graph') as 'graph' | 'baseline';
// Thesis 5.7: temperature 0 + repeated runs (median/IQR computed at analysis).
const temperature = Number(arg('--temperature', '0'));
const repeats = Math.max(1, Number(arg('--repeats', '1')) || 1);

// Mirrors interpreter.ts DEFAULT_ANSWER_JOB so the baseline answer prompt is
// byte-identical to the graph arm's (only the evidence differs).
const BASELINE_PLAN = (q: string): QueryPlan => ({
  description: q,
  tags: [],
  filters: {
    dataset_id: datasetId, file_ids: [], min_w_chunk: 0, min_relevance_to_file: 0,
    limit: retrievalLimit,
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
  // App.jsx pins the HERB graph to the `herb` database; mirror that, allow override.
  database: cfg('NEO4J_DATABASE', 'herb'),
};
const openaiKey = cfg('OPENAI_API_KEY', '');
const anthropicKey = cfg('ANTHROPIC_API_KEY', '');

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

// --- main ------------------------------------------------------------------

async function main(): Promise<void> {
  if (!anthropicKey && model.startsWith('claude')) {
    throw new Error('ANTHROPIC_API_KEY (or VITE_ANTHROPIC_API_KEY) is not set.');
  }
  if (!neo4jCfg.password) {
    throw new Error('NEO4J_PASSWORD (or VITE_NEO4J_PASSWORD) is not set.');
  }
  preflightModel();

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
        ? 'content-only full-text (no tags/grounding/gate)'
        : `limit=${retrievalLimit} groundingK=${groundingK} minSim=${minSim}`}\n` +
      `  exclude   : ${excludeSections.length ? excludeSections.join(',') : '(none)'}` +
      `${dryRun ? '\n  DRY RUN — answer LLM skipped' : ''}\n`,
  );

  // Stream rows to disk as each question completes. A long run makes many
  // native (onnxruntime/transformers.js) calls and can hard-crash the process;
  // a single end-of-run write would lose everything. Per-row append leaves a
  // valid partial JSONL. Default is RESUME: an existing out file is kept and
  // already-done ids are skipped, so re-running after a crash converges to a
  // complete set. `--fresh` truncates and starts over.
  const doneIds = new Set<string>();
  if (!fresh && existsSync(outPath)) {
    for (const raw of readFileSync(outPath, 'utf-8').split('\n')) {
      const s = raw.trim();
      if (!s) continue;
      try { doneIds.add(String((JSON.parse(s) as { id?: unknown }).id)); } catch { /* skip bad line */ }
    }
  } else {
    writeFileSync(outPath, '', 'utf-8');
  }
  let ok = 0;
  let errored = 0;
  let resumed = 0;

  const totalUnits = slice.length * repeats;
  let unit = 0;

  for (let i = 0; i < slice.length; i++) {
    const { id, question, reference } = slice[i];
    for (let rep = 1; rep <= repeats; rep++) {
      unit++;
      const rowId = repeats > 1 ? `${id}#r${rep}` : id;
      if (doneIds.has(rowId)) {
        resumed++;
        console.log(`  [${unit}/${totalUnits}] ${rowId} … skip (already in out)`);
        continue;
      }
      const t0 = Date.now();
      process.stdout.write(`  [${unit}/${totalUnits}] ${rowId} (${mode}) … `);

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

      try {
        let chunks: RetrievedChunk[];
        let planForAnswer: QueryPlan;

        if (mode === 'baseline') {
          planForAnswer = BASELINE_PLAN(question);
          chunks = await retrieveBaselineContent(question, neo4jCfg, {
            limit: retrievalLimit,
            datasetId,
            ...(excludeSections.length ? { excludeSections } : {}),
          });
          meta.warnings = [];
        } else {
          const plan = await interpretPrompt(
            question, interpreterModel, openaiKey, anthropicKey, datasetId, temperature,
          );
          planForAnswer = {
            ...plan,
            filters: { ...plan.filters, dataset_id: datasetId, limit: retrievalLimit },
          };
          chunks = await retrieveChunks(planForAnswer, neo4jCfg, {
            limit: retrievalLimit,
            datasetId,
            groundingK,
            minSim,
            tagsEnabled: true,
            ...(excludeSections.length ? { excludeSections } : {}),
          });
          meta.plan_description = planForAnswer.description;
          meta.warnings = planForAnswer.warnings;
          meta.gate = planForAnswer.filters.gate;
          meta.grounding = planForAnswer.grounding ?? [];
        }

        contexts = chunks.map((c) => c.content).filter(Boolean);
        meta.n_chunks = chunks.length;
        meta.chunk_ids = chunks.map((c) => c.chunkId);
        meta.file_ids = [...new Set(chunks.map((c) => c.fileId))];

        if (!dryRun) {
          const ans = await generateAnswer(
            question, planForAnswer, chunks, model, openaiKey, anthropicKey, promptMode, temperature,
          );
          response = ans.response;
          meta.tokens = { answer_in: ans.tokensIn, answer_out: ans.tokensOut };
        }
        meta.elapsed_ms = Date.now() - t0;
        meta.error = null;
        ok++;
        console.log(`ok (${contexts.length} chunks${dryRun ? '' : `, ${response.length} chars`})`);
      } catch (err) {
        meta.elapsed_ms = Date.now() - t0;
        meta.error = err instanceof Error ? err.message : String(err);
        errored++;
        console.log(`ERROR: ${meta.error}`);
      }

      appendFileSync(
        outPath,
        JSON.stringify({
          id: rowId,
          question,
          user_input: question,
          retrieved_contexts: contexts,
          response,
          answer: response,
          reference: reference ?? null,
          meta,
        }) + '\n',
        'utf-8',
      );
    }
  }

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
