import { chat } from './llm';
import type { QueryPlan } from './interpreter';
import type { RetrievedChunk } from './retrieval';

export interface AnswerResult {
  response: string;
  tokensIn: number;
  tokensOut: number;
}

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
  openaiKey: string,
  anthropicKey: string,
): Promise<AnswerResult> {
  const system =
    `You are a retrieval-augmented assistant. Answer using only the provided chunks.\n` +
    `Evidence policy: ${plan.answer_job.evidence_policy}.\n` +
    `If evidence is insufficient: ${plan.answer_job.missing_evidence_policy}.\n` +
    `Cite chunks by their id number in brackets, e.g. [1] or [2,4].`;

  const userContent = chunks.length
    ? `Query: ${prompt}\n\nRetrieved evidence:\n\n${formatChunks(chunks)}`
    : `Query: ${prompt}\n\n(No chunks were retrieved — say insufficient evidence.)`;

  const resp = await chat(
    [{ role: 'system', content: system }, { role: 'user', content: userContent }],
    model,
    openaiKey,
    anthropicKey,
    { maxTokens: 1024 },
  );

  return { response: resp.text, tokensIn: resp.tokensIn, tokensOut: resp.tokensOut };
}
