import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';

export interface LlmMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface LlmResult {
  text: string;
  tokensIn: number;
  tokensOut: number;
}

export interface ChatOptions {
  maxTokens?: number;
  /** When true, ask the provider to return strict JSON only. */
  jsonMode?: boolean;
  /** Sampling temperature. Omitted → provider default (unchanged app
   *  behaviour). The eval harness passes 0 for deterministic, low-variance
   *  runs (thesis 5.7: temperature = 0, repeated runs). */
  temperature?: number;
}

function isClaudeModel(model: string) {
  return model.startsWith('claude');
}

export async function chat(
  messages: LlmMessage[],
  model: string,
  openaiKey: string,
  anthropicKey: string,
  opts: ChatOptions = {},
): Promise<LlmResult> {
  const maxTokens = opts.maxTokens ?? 1024;

  if (isClaudeModel(model)) {
    if (!anthropicKey) throw new Error('Anthropic API key not set (VITE_ANTHROPIC_API_KEY).');
    const client = new Anthropic({ apiKey: anthropicKey, dangerouslyAllowBrowser: true });
    const system = messages.find(m => m.role === 'system')?.content ?? '';
    const rest = messages.filter(m => m.role !== 'system') as Anthropic.MessageParam[];

    // For JSON mode, prefill the assistant turn with `{` so the model can only
    // emit a JSON object body (this is the documented Anthropic JSON pattern).
    const finalMessages: Anthropic.MessageParam[] = opts.jsonMode
      ? [...rest, { role: 'assistant', content: '{' }]
      : rest;

    const resp = await client.messages.create({
      model,
      max_tokens: maxTokens,
      system,
      messages: finalMessages,
      ...(opts.temperature != null ? { temperature: opts.temperature } : {}),
    });

    const body = resp.content[0]?.type === 'text' ? resp.content[0].text : '';
    const text = opts.jsonMode ? `{${body}` : body;
    return { text, tokensIn: resp.usage.input_tokens, tokensOut: resp.usage.output_tokens };
  }

  if (!openaiKey) throw new Error('OpenAI API key not set (VITE_OPENAI_API_KEY).');
  const client = new OpenAI({ apiKey: openaiKey, dangerouslyAllowBrowser: true });
  const resp = await client.chat.completions.create({
    model,
    max_tokens: maxTokens,
    messages,
    ...(opts.temperature != null ? { temperature: opts.temperature } : {}),
    ...(opts.jsonMode ? { response_format: { type: 'json_object' as const } } : {}),
  });
  const text = resp.choices[0]?.message?.content ?? '';
  return {
    text,
    tokensIn: resp.usage?.prompt_tokens ?? 0,
    tokensOut: resp.usage?.completion_tokens ?? 0,
  };
}
