/**
 * Prompt-tag embedding for the grounding step.
 *
 * Runs intfloat/e5-small-v2 in the browser via transformers.js (ONNX/WASM) —
 * the SAME model the backend uses to embed corpus `:Tag` nodes
 * (`tagging/pipeline.py:stage_embed_tags`). Same weights → vectors are
 * comparable, so kNN against the `tag_embedding` index is meaningful.
 *
 * Symmetric with the corpus side: the backend embeds each `:Tag` as
 * `passage: <name>. <its most-central chunk descriptions>`
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
    extractorPromise = pipeline('feature-extraction', 'Xenova/e5-small-v2', {
      quantized: false,
    }).catch((e) => {
      extractorPromise = null; // let a later run retry instead of caching the failure
      throw new Error(
        'Failed to load the e5-small-v2 grounding model from ' +
        '/models/Xenova/e5-small-v2/. Ensure the bundled model files are present ' +
        `(public/models/Xenova/e5-small-v2/). Underlying error: ${(e as Error).message}`,
      );
    });
  }
  return extractorPromise;
}

/** Mirror of backend `_tag_embed_text`: `passage: <readable name>. <ctx>`,
 *  ctx whitespace-collapsed and capped at 900 chars (empty ctx → name only). */
function tagEmbedText(name: string, context: string): string {
  const readable = readableTag(name);
  const ctx = context.replace(/\s+/g, ' ').trim().slice(0, 900);
  const body = ctx ? `${readable}. ${ctx}` : readable;
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
  const inputs = tagNames.map((n) => tagEmbedText(n, description));
  const out = await extractor(inputs, { pooling: 'mean', normalize: true });
  return out.tolist() as number[][];
}
