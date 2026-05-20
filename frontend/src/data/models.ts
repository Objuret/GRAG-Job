/**
 * Model + provider registry. Single source of truth for:
 *  - which providers the app knows about (env-key name + OpenAI-compatible base URL)
 *  - which model ids are pre-listed in the Run Builder dropdown
 *  - the model id → provider routing used by services/llm.ts
 *
 * Adding a model: append to MODELS. Adding a provider: add to PROVIDERS and
 * thread its env var through normalizeConnConfig in App.jsx.
 *
 * DeepSeek, Ollama Cloud, and Groq are all OpenAI-API-compatible, so they
 * reuse the OpenAI SDK in llm.ts with a per-provider baseURL override.
 * Anthropic uses its own SDK because the message shape differs.
 */

export type Provider = 'anthropic' | 'openai' | 'deepseek' | 'ollama' | 'groq';

export interface ProviderConfig {
  id: Provider;
  label: string;
  /** Vite env var name the key is read from (used in error messages). */
  envKeyVar: string;
  /** OpenAI-compatible API root. Undefined for Anthropic (uses its own SDK). */
  baseURL?: string;
}

export const PROVIDERS: Record<Provider, ProviderConfig> = {
  anthropic: { id: 'anthropic', label: 'Anthropic',    envKeyVar: 'VITE_ANTHROPIC_API_KEY' },
  openai:    { id: 'openai',    label: 'OpenAI',       envKeyVar: 'VITE_OPENAI_API_KEY' },
  deepseek:  { id: 'deepseek',  label: 'DeepSeek',     envKeyVar: 'VITE_DEEPSEEK_API_KEY', baseURL: 'https://api.deepseek.com' },
  ollama:    { id: 'ollama',    label: 'Ollama Cloud', envKeyVar: 'VITE_OLLAMA_API_KEY',   baseURL: 'https://ollama.com/v1' },
  groq:      { id: 'groq',      label: 'Groq',         envKeyVar: 'VITE_GROQ_API_KEY',     baseURL: 'https://api.groq.com/openai/v1' },
};

export interface ModelEntry {
  /** Exact id sent to the provider API. */
  id: string;
  /** Dropdown label. */
  label: string;
  provider: Provider;
}

/** Pre-listed models. The Run Builder lets you type any id, but only ids here
 *  are dropdown-selectable and resolve to a provider without ambiguity. */
export const MODELS: ModelEntry[] = [
  // DeepSeek — primary workhorse (cheapest serious model)
  { id: 'deepseek-chat',           label: 'DeepSeek-V3 — cheap workhorse',       provider: 'deepseek' },
  { id: 'deepseek-reasoner',       label: 'DeepSeek-R1 — cheap reasoning',       provider: 'deepseek' },
  // Ollama Cloud — free tier (rate-limited; do not trust for thesis numbers)
  { id: 'gpt-oss:120b',            label: 'gpt-oss 120B — Ollama Cloud (free)',  provider: 'ollama' },
  { id: 'qwen3-coder:480b',        label: 'Qwen3 Coder 480B — Ollama Cloud (free)', provider: 'ollama' },
  { id: 'deepseek-v3.1:671b',      label: 'DeepSeek V3.1 671B — Ollama Cloud (free)', provider: 'ollama' },
  // Groq — fast paid host for the same open-weights models
  { id: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B — Groq (fast)',         provider: 'groq' },
  { id: 'gpt-oss-120b',            label: 'gpt-oss 120B — Groq',                 provider: 'groq' },
  { id: 'deepseek-r1-distill-llama-70b', label: 'DeepSeek-R1 Distill 70B — Groq', provider: 'groq' },
  // Anthropic — optional closed-model anchor for the thesis table
  { id: 'claude-haiku-4-5',        label: 'Claude Haiku 4.5 — cheapest Claude',  provider: 'anthropic' },
  { id: 'claude-sonnet-4-6',       label: 'Claude Sonnet 4.6',                   provider: 'anthropic' },
  { id: 'claude-opus-4-7',         label: 'Claude Opus 4.7 — expensive anchor',  provider: 'anthropic' },
];

const MODEL_BY_ID: Map<string, ModelEntry> = new Map(MODELS.map((m) => [m.id, m]));

/**
 * Resolve a model id to its provider. Loud on unknown ids — no silent OpenAI
 * fallback like the old `startsWith('claude')` router did.
 */
export function providerOf(modelId: string): Provider {
  const m = MODEL_BY_ID.get(modelId);
  if (m) return m.provider;
  throw new Error(
    `Unknown model "${modelId}". Add it to MODELS in src/data/models.ts, ` +
    `or pick a listed id (${MODELS.map((x) => x.id).join(', ')}).`,
  );
}

/** Bag of provider keys read from VITE_* env, passed to llm.chat(). */
export interface ProviderKeys {
  anthropic?: string;
  openai?: string;
  deepseek?: string;
  ollama?: string;
  groq?: string;
}

/** Throw a precise error naming the missing env var. */
export function requireKey(provider: Provider, keys: ProviderKeys, modelId: string): string {
  const key = keys[provider];
  if (!key) {
    throw new Error(
      `${PROVIDERS[provider].label} API key not set (${PROVIDERS[provider].envKeyVar}). ` +
      `Required for model "${modelId}".`,
    );
  }
  return key;
}
