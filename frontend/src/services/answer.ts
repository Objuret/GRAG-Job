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

function formatChunks(chunks: RetrievedChunk[]): string {
  return chunks.map((c, i) => {
    const meta = [
      `score=${c.score.toFixed(3)}`,
      c.relevanceToFile != null ? `rel=${c.relevanceToFile.toFixed(2)}` : null,
      c.description ? `"${c.description}"` : null,
    ].filter(Boolean).join(' ');
    return `<chunk id="${i + 1}" ${meta}>\n${c.content.slice(0, 1800)}\n</chunk>`;
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
): Promise<AnswerResult> {
  const system =
    `You are a retrieval-augmented assistant. Answer using only the provided chunks.\n` +
    `Evidence policy: ${plan.answer_job.evidence_policy}.\n` +
    `If evidence is insufficient: ${plan.answer_job.missing_evidence_policy}.\n` +
    `Cite chunks by their id number in brackets, e.g. [1] or [2,4].`;

  const evidence = chunks.length
    ? formatChunks(chunks)
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
