import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';
import { PROVIDERS, providerOf, requireKey, type ProviderKeys } from '../data/models';

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
  /** Optional sampling temperature. The app leaves this unset; eval harnesses
   * pass 0 for reproducible runs. */
  temperature?: number;
}

export type { ProviderKeys };

/**
 * Single chat entry point. The model id determines the provider via the
 * registry in src/data/models.ts; the provider determines the SDK (Anthropic
 * uses its own; everything else is OpenAI-API-compatible and reuses the OpenAI
 * SDK with a per-provider baseURL).
 *
 * Loud-fails on (a) unknown model id and (b) missing key for the resolved
 * provider — never a silent fall-through to "the other" provider.
 */
export async function chat(
  messages: LlmMessage[],
  model: string,
  keys: ProviderKeys,
  opts: ChatOptions = {},
): Promise<LlmResult> {
  const maxTokens = opts.maxTokens ?? 1024;
  const provider = providerOf(model);
  const apiKey = requireKey(provider, keys, model);

  if (provider === 'anthropic') {
    const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
    const system = messages.find(m => m.role === 'system')?.content ?? '';
    const rest = messages.filter(m => m.role !== 'system') as Anthropic.MessageParam[];

    // For JSON mode, prefill the assistant turn with `{` so the model can only
    // emit a JSON object body (documented Anthropic JSON pattern).
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

  // OpenAI-API-compatible: OpenAI, DeepSeek, Ollama Cloud, Groq.
  // `baseURL` is undefined for native OpenAI (SDK default), set for the others.
  const baseURL = PROVIDERS[provider].baseURL;
  const client = new OpenAI({ apiKey, baseURL, dangerouslyAllowBrowser: true });
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
