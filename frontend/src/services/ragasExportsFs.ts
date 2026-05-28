/** Repo-root folder for RAGAS configs, JSONL runs, and report JSON (dev server writes). */
export const RAGAS_EXPORTS_DIR = 'ragas_exports';

const API = '/__ragas_exports';

export function isRagasExportsFsAvailable(): boolean {
  return import.meta.env.DEV;
}

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data?.error === 'string' ? data.error : res.statusText;
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data as T;
}

export async function listRagasExports(): Promise<{ name: string; size: number; mtimeMs: number }[]> {
  const data = await apiJson<{ files: { name: string; size: number; mtimeMs: number }[] }>(`${API}/list`);
  return data.files || [];
}

export async function readRagasExport(name: string): Promise<string> {
  const q = new URLSearchParams({ name });
  const data = await apiJson<{ text: string }>(`${API}/read?${q}`);
  return data.text;
}

export async function writeRagasExport(name: string, text: string): Promise<string> {
  const data = await apiJson<{ path: string }>(`${API}/write`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, text }),
  });
  return data.path;
}

export async function ragasExportExists(name: string): Promise<boolean> {
  const q = new URLSearchParams({ name });
  const data = await apiJson<{ exists: boolean }>(`${API}/exists?${q}`);
  return Boolean(data.exists);
}

/** Join optional subfolder under ragas_exports (no leading slash, no ..). */
export function joinRagasExportPath(subdir: string, filename: string): string {
  const parts = [subdir, filename]
    .map((p) => String(p || '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, ''))
    .filter(Boolean);
  return parts.join('/');
}
