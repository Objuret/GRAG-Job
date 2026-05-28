import { chat, type LlmMessage, type ProviderKeys } from './llm';
import type { QueryPlan } from './interpreter';
import type { RetrievedChunk } from './retrieval';

export interface AnswerResult {
  response: string;
  tokensIn: number;
  tokensOut: number;
}

/**
 * How the prompt reaches the answer LLM:
 *  - 'raw'     clean prompt only — the literal user prompt, no system framing
 *              and no retrieved evidence (what the user typed, verbatim).
 *  - 'context' structured for API (default) — system evidence policy + a single
 *              user turn embedding the formatted retrieved chunks.
 *  - 'hybrid'  context + system — system policy, the raw prompt as its own
 *              clean turn, plus the retrieved evidence as a separate turn.
 */
export type AnswerMode = 'raw' | 'context' | 'hybrid';

/** Headless export: scrub HERB bytes + cap evidence sent to the answer API. */
export interface AnswerCallOptions {
  /** Top-N chunks by score for the answer/evidence budget (0 = all retrieved). */
  maxAnswerChunks?: number;
  maxChunkChars?: number;
  scrubForApi?: boolean;
}

/** HERB slack/raw exports can break OpenAI-compatible JSON request bodies. */
export function scrubApiText(text: string): string {
  let out = '';
  for (let i = 0; i < text.length; i++) {
    const cp = text.charCodeAt(i);
    if (cp >= 0xd800 && cp <= 0xdbff) {
      const next = text.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) { out += text[i] + text[i + 1]; i++; continue; }
      continue;
    }
    if (cp >= 0xdc00 && cp <= 0xdfff) continue;
    if (cp === 0 || (cp < 0x20 && cp !== 0x09 && cp !== 0x0a && cp !== 0x0d)) continue;
    out += text[i];
  }
  // Truncation can leave `\`, `\u`, or partial `\uXXXX` at the end — some APIs reject the JSON body.
  out = out.replace(/\\u[0-9a-fA-F]{0,3}$/g, '');
  out = out.replace(/\\+$/g, '');
  return out;
}

/** Same slice the answer LLM sees — export/RAGAS must use this for `retrieved_contexts`. */
export function selectEvidenceChunks(
  chunks: RetrievedChunk[],
  opts: AnswerCallOptions = {},
): RetrievedChunk[] {
  const maxChars = opts.maxChunkChars ?? 1800;
  let list = [...chunks].sort((a, b) => b.score - a.score);
  const cap = opts.maxAnswerChunks ?? 0;
  if (cap > 0) list = list.slice(0, cap);
  return list.map((c) => {
    let content = c.content.slice(0, maxChars);
    let description = c.description;
    if (opts.scrubForApi) {
      content = scrubApiText(content);
      if (description != null) description = scrubApiText(description);
    }
    return { ...c, content, ...(description != null ? { description } : {}) };
  });
}

function formatChunks(chunks: RetrievedChunk[]): string {
  return chunks.map((c, i) => {
    const meta = [
      `score=${c.score.toFixed(3)}`,
      c.relevanceToFile != null ? `rel=${c.relevanceToFile.toFixed(2)}` : null,
      c.description ? `"${c.description}"` : null,
    ].filter(Boolean).join(' ');
    return `<chunk id="${i + 1}" ${meta}>\n${c.content}\n</chunk>`;
  }).join('\n\n');
}

export async function generateAnswer(
  prompt: string,
  plan: QueryPlan,
  chunks: RetrievedChunk[],
  model: string,
  keys: ProviderKeys,
  mode: AnswerMode = 'context',
  temperature?: number,
  callOpts: AnswerCallOptions = {},
): Promise<AnswerResult> {
  const system =
    `You are a retrieval-augmented assistant. Answer using only the provided chunks.\n` +
    `Evidence policy: ${plan.answer_job.evidence_policy}.\n` +
    `If evidence is insufficient: ${plan.answer_job.missing_evidence_policy}.\n` +
    `Cite chunks by their id number in brackets, e.g. [1] or [2,4].`;

  const answerChunks = selectEvidenceChunks(chunks, callOpts);
  const evidence = answerChunks.length
    ? formatChunks(answerChunks)
    : '(No chunks were retrieved — say insufficient evidence.)';

  let messages: LlmMessage[];
  if (mode === 'raw') {
    messages = [{ role: 'user', content: prompt }];
  } else if (mode === 'hybrid') {
    messages = [
      { role: 'system', content: system },
      { role: 'user', content: prompt },
      { role: 'user', content: `Retrieved evidence:\n\n${evidence}` },
    ];
  } else {
    messages = [
      { role: 'system', content: system },
      { role: 'user', content: `Query: ${prompt}\n\nRetrieved evidence:\n\n${evidence}` },
    ];
  }

  const resp = await chat(messages, model, keys, {
    maxTokens: 1024,
    ...(temperature != null ? { temperature } : {}),
  });

  return { response: resp.text, tokensIn: resp.tokensIn, tokensOut: resp.tokensOut };
}
