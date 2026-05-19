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
import { readFileSync, existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { env as hfEnv } from '@xenova/transformers';

import { interpretPrompt } from '../src/services/interpreter';
import { retrieveChunks } from '../src/services/retrieval';
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

const questionsPath = resolve(
  arg('--questions', join(SCRIPT_DIR, 'ragas-questions.example.jsonl'))!,
);
const outPath = resolve(arg('--out', join(REPO_ROOT, 'backend', 'evaluation', 'ragas_samples.jsonl'))!);
const maxQuestions = Number(arg('--max', '0')) || 0; // 0 = all
const dryRun = hasFlag('--dry-run'); // interpret+retrieve only, skip the answer LLM

const model = arg('--model', cfg('MODEL', 'claude-haiku-4-5'))!;
const interpreterModel = arg('--interpreter-model', cfg('INTERPRETER_MODEL', '')) || model;
const promptMode = (arg('--prompt-mode', cfg('PROMPT_MODE', 'context')) as AnswerMode);
const datasetId = arg('--dataset', cfg('DATASET_ID', 'Salesforce__HERB')) || null;
const retrievalLimit = Number(arg('--limit', cfg('RETRIEVAL_LIMIT', '20'))) || 20;
const groundingK = Number(cfg('GROUNDING_K', '10')) || 10;
const minSim = Number(cfg('MIN_SIM', '0')) || 0;

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
        items.push({ id: String(o.id ?? `q${i + 1}`), question: String(o.question ?? '') });
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
      if (line.startsWith('{')) {
        try {
          const o = JSON.parse(line) as Record<string, unknown>;
          question = String(o.question ?? o.user_input ?? '');
          id = String(o.id ?? `q${n}`);
        } catch {
          /* not JSON — treat the whole line as the question */
        }
      }
      if (question) items.push({ id, question });
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
      `  questions : ${slice.length} from ${questionsPath}\n` +
      `  out       : ${outPath}\n` +
      `  graph     : ${neo4jCfg.uri} db=${neo4jCfg.database} dataset=${datasetId}\n` +
      `  model     : answer=${model} interpret=${interpreterModel} mode=${promptMode}\n` +
      `  retrieval : limit=${retrievalLimit} groundingK=${groundingK} minSim=${minSim}` +
      `${dryRun ? '\n  DRY RUN — answer LLM skipped' : ''}\n`,
  );

  const rows: string[] = [];
  let ok = 0;
  let errored = 0;

  for (let i = 0; i < slice.length; i++) {
    const { id, question } = slice[i];
    const t0 = Date.now();
    process.stdout.write(`  [${i + 1}/${slice.length}] ${id} … `);

    const meta: Record<string, unknown> = {
      model,
      interpreter_model: interpreterModel,
      prompt_mode: promptMode,
      dataset_id: datasetId,
      database: neo4jCfg.database,
    };
    let contexts: string[] = [];
    let response = '';

    try {
      const plan = await interpretPrompt(question, interpreterModel, openaiKey, anthropicKey, datasetId);
      const scopedPlan = {
        ...plan,
        filters: { ...plan.filters, dataset_id: datasetId, limit: retrievalLimit },
      };
      const chunks = await retrieveChunks(scopedPlan, neo4jCfg, {
        limit: retrievalLimit,
        datasetId,
        groundingK,
        minSim,
        tagsEnabled: true,
      });
      contexts = chunks.map((c) => c.content).filter(Boolean);

      meta.plan_description = scopedPlan.description;
      meta.warnings = scopedPlan.warnings;
      meta.gate = scopedPlan.filters.gate;
      meta.grounding = scopedPlan.grounding ?? [];
      meta.n_chunks = chunks.length;
      meta.chunk_ids = chunks.map((c) => c.chunkId);
      meta.file_ids = [...new Set(chunks.map((c) => c.fileId))];

      if (!dryRun) {
        const ans = await generateAnswer(
          question,
          scopedPlan,
          chunks,
          model,
          openaiKey,
          anthropicKey,
          promptMode,
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

    rows.push(
      JSON.stringify({
        id,
        question,
        user_input: question,
        retrieved_contexts: contexts,
        response,
        answer: response,
        meta,
      }),
    );
  }

  writeFileSync(outPath, rows.join('\n') + '\n', 'utf-8');
  console.log(
    `\nDone. ${ok} ok, ${errored} errored, ${slice.length} total.\n` +
      `Wrote ${outPath}`,
  );
  if (errored > 0) process.exitCode = 1;
}

main().catch((err) => {
  console.error(`\nFATAL: ${err instanceof Error ? err.message : String(err)}`);
  process.exit(2);
});
