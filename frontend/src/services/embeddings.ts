/**
 * Prompt-tag embedding for the grounding step.
 *
 * Runs intfloat/e5-small-v2 in the browser via transformers.js (ONNX/WASM) —
 * the SAME model the backend uses to embed corpus `:Tag` nodes
 * (`tagging/pipeline.py:stage_embed_tags`). Same weights → vectors are
 * comparable, so kNN against the `tag_embedding` index is meaningful.
 *
 * e5 requires the prefix convention: corpus tags are embedded as `passage:`,
 * prompt tags here as `query:`.
 */
import { pipeline, type FeatureExtractionPipeline } from '@xenova/transformers';

// Mirror of backend `_readable_tag`: snake_case → words.
function readableTag(name: string): string {
  return name.replace(/_/g, ' ').trim();
}

let extractorPromise: Promise<FeatureExtractionPipeline> | null = null;

function getExtractor(): Promise<FeatureExtractionPipeline> {
  if (!extractorPromise) {
    extractorPromise = pipeline('feature-extraction', 'Xenova/e5-small-v2');
  }
  return extractorPromise;
}

/**
 * Embed cleaned prompt-tag names as e5 queries. Returns one unit-normalised
 * 384-d vector per input, aligned by index.
 */
export async function embedPromptTags(tagNames: string[]): Promise<number[][]> {
  if (!tagNames.length) return [];
  const extractor = await getExtractor();
  const inputs = tagNames.map((n) => `query: ${readableTag(n)}`);
  const out = await extractor(inputs, { pooling: 'mean', normalize: true });
  return out.tolist() as number[][];
}
