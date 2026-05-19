/**
 * Prompt-tag embedding for the grounding step.
 *
 * Runs intfloat/e5-small-v2 in the browser via transformers.js (ONNX/WASM) —
 * the SAME model the backend uses to embed corpus `:TagEmbedding` nodes
 * (`tagging/pipeline.py:stage_embed_tags`). Same weights → vectors are
 * comparable, so kNN against the `tag_facet_embedding` index is meaningful.
 *
 * Symmetric with the corpus side: the backend embeds each `(tag, facet)` and
 * `(tag, all)` use as `passage: <name>. <facet scope>. <central chunk descriptions>`
 * (`tagging/pipeline.py:_tag_embed_text`). To compare like with like, a prompt
 * tag is embedded the same way — `passage: <name>. <prompt description>` —
 * where the Pass-1 prompt description is the query-side analogue of the
 * corpus-side chunk descriptions. Both sides use the `passage:` prefix and the
 * 900-char context cap; there is no asymmetric `query:` path.
 */
import { env, pipeline, type FeatureExtractionPipeline } from '@xenova/transformers';

// Serve the model from the app itself, never from Hugging Face at runtime.
// The ONNX + tokenizer files live in `public/models/Xenova/e5-small-v2/`
// (vite serves `public/` at the web root), so transformers.js resolves
// `Xenova/e5-small-v2` to `/models/Xenova/e5-small-v2/...` on this origin.
// This is the browser analogue of the backend's on-disk HF cache: the model
// is fetched once at build/checkout time, not on every cold browser cache.
env.allowLocalModels = true;
env.allowRemoteModels = false;        // hard-fail loud instead of silently hitting HF
env.localModelPath = '/models';
env.useBrowserCache = false;          // avoid stale CacheStorage JSON/HTML poisoning

const MODEL_ID = 'Xenova/e5-small-v2';
const MODEL_BASE = `/models/${MODEL_ID}`;
const JSON_ASSETS = [
  'config.json',
  'tokenizer.json',
  'tokenizer_config.json',
  'special_tokens_map.json',
  // transformers.js asks for this optional file; Vite otherwise returns the
  // HTML app shell for the missing path, which surfaces as a vague JSON.parse
  // error. We bundle an empty object and verify it explicitly.
  'generation_config.json',
];

let localModelCheck: Promise<void> | null = null;

async function clearStaleModelJsonCache(): Promise<void> {
  if (typeof caches === 'undefined') return;
  try {
    const cache = await caches.open('transformers-cache');
    await Promise.all(JSON_ASSETS.map((file) => cache.delete(`${MODEL_BASE}/${file}`)));
  } catch {
    // CacheStorage can be unavailable in some browser contexts; asset preflight
    // still catches broken network responses before the model loader runs.
  }
}

async function verifyLocalModelAssets(): Promise<void> {
  if (typeof fetch !== 'function') return;
  if (!localModelCheck) {
    localModelCheck = (async () => {
      for (const file of JSON_ASSETS) {
        const path = `${MODEL_BASE}/${file}`;
        const res = await fetch(path, { cache: 'no-store' });
        const text = await res.text();
        if (!res.ok) {
          throw new Error(`Missing grounding model asset: ${path} returned HTTP ${res.status}.`);
        }
        try {
          JSON.parse(text);
        } catch (e) {
          const prefix = text.trim().slice(0, 40);
          throw new Error(
            `Grounding model asset is not valid JSON: ${path}. ` +
            `The server returned ${prefix ? JSON.stringify(prefix) : 'an empty body'}. ` +
            `Run \`npm run assets:assemble\` and restart Vite if the public model folder changed. ` +
            `Parser said: ${(e as Error).message}`,
            { cause: e },
          );
        }
      }
      await clearStaleModelJsonCache();
      const modelPath = `${MODEL_BASE}/onnx/model.onnx`;
      const modelRes = await fetch(modelPath, { method: 'HEAD', cache: 'no-store' });
      if (!modelRes.ok) {
        throw new Error(`Missing grounding model weights: ${modelPath} returned HTTP ${modelRes.status}.`);
      }
      const modelType = modelRes.headers.get('content-type') || '';
      const modelSize = Number(modelRes.headers.get('content-length') || 0);
      if (modelType.includes('text/html') || (modelSize > 0 && modelSize < 1_000_000)) {
        throw new Error(
          `Grounding model weights look invalid: ${modelPath} returned ` +
          `${modelType || 'unknown content-type'} with ${modelSize || 'unknown'} bytes.`,
        );
      }
    })().catch((e) => {
      localModelCheck = null;
      throw e;
    });
  }
  return localModelCheck;
}

// Mirror of backend `_readable_tag`: snake_case → words.
function readableTag(name: string): string {
  return name.replace(/_/g, ' ').trim();
}

let extractorPromise: Promise<FeatureExtractionPipeline> | null = null;

function getExtractor(): Promise<FeatureExtractionPipeline> {
  if (!extractorPromise) {
    // quantized:false → load full fp32 onnx/model.onnx, matching the backend's
    // fp32 sentence-transformers vectors exactly. transformers.js defaults to
    // the int8 model_quantized.onnx, which would drift from the corpus vectors.
    extractorPromise = verifyLocalModelAssets()
      .then(() => pipeline('feature-extraction', MODEL_ID, { quantized: false }))
      .catch((e) => {
        extractorPromise = null; // let a later run retry instead of caching the failure
        throw new Error(
          'Failed to load the e5-small-v2 grounding model from ' +
          `${MODEL_BASE}/. Ensure the bundled model files are present ` +
          `(public/models/Xenova/e5-small-v2/). Underlying error: ${(e as Error).message}`,
          { cause: e },
        );
      });
  }
  return extractorPromise;
}

/** Mirror of backend `_tag_embed_text`: `passage: <readable name>. <ctx>`,
 *  ctx whitespace-collapsed and capped at 900 chars (empty ctx → name only). */
export type EmbedFacet = 'topic' | 'entities' | 'activity' | 'temporal' | 'evidence' | 'all';

export interface PromptTagFacetInput {
  name: string;
  facet: EmbedFacet;
}

function tagEmbedText(name: string, context: string, facet: EmbedFacet = 'all'): string {
  const readable = readableTag(name);
  const facetText = facet === 'all' ? 'all facets' : `${facet} facet`;
  const ctx = context.replace(/\s+/g, ' ').trim().slice(0, 900);
  const body = ctx ? `${readable}. ${facetText}. ${ctx}` : `${readable}. ${facetText}`;
  return `passage: ${body}`;
}

/**
 * Embed prompt tags the same way the backend embedded corpus tags: name +
 * description prose, `passage:` prefix. `description` is the Pass-1 prompt
 * description (the query-side stand-in for corpus chunk descriptions). Returns
 * one unit-normalised 384-d vector per input, aligned by index.
 */
export async function embedPromptTags(
  tagNames: string[],
  description = '',
): Promise<number[][]> {
  if (!tagNames.length) return [];
  const extractor = await getExtractor();
  const inputs = tagNames.map((n) => tagEmbedText(n, description, 'all'));
  const out = await extractor(inputs, { pooling: 'mean', normalize: true });
  return out.tolist() as number[][];
}

export async function embedPromptTagFacets(
  items: PromptTagFacetInput[],
  description = '',
): Promise<number[][]> {
  if (!items.length) return [];
  const extractor = await getExtractor();
  const inputs = items.map((item) => tagEmbedText(item.name, description, item.facet));
  const out = await extractor(inputs, { pooling: 'mean', normalize: true });
  return out.tolist() as number[][];
}
