/** Gold-set loading — shared by all RAGAS export arms. */
import { readFileSync, existsSync } from 'node:fs';

import type { GoldQuestion } from '../../src/rag/exportContract';

export type { GoldQuestion };

export function loadQuestions(path: string): GoldQuestion[] {
  if (!existsSync(path)) {
    throw new Error(`Questions file not found: ${path}`);
  }
  const text = readFileSync(path, 'utf-8');
  const items: GoldQuestion[] = [];
  if (path.endsWith('.json')) {
    const parsed = JSON.parse(text);
    const arr = Array.isArray(parsed) ? parsed : parsed.questions ?? [];
    arr.forEach((q: unknown, i: number) => {
      if (typeof q === 'string') items.push({ id: `q${i + 1}`, question: q });
      else if (q && typeof q === 'object') {
        const o = q as Record<string, unknown>;
        const ref = o.reference ?? o.ground_truth;
        items.push({
          id: String(o.id ?? `q${i + 1}`),
          question: String(o.question ?? ''),
          ...(ref != null ? { reference: String(ref) } : {}),
        });
      }
    });
  } else {
    let n = 0;
    for (const raw of text.split('\n')) {
      const line = raw.trim();
      if (!line || line.startsWith('#')) continue;
      n++;
      let question = line;
      let id = `q${n}`;
      let reference: string | undefined;
      if (line.startsWith('{')) {
        try {
          const o = JSON.parse(line) as Record<string, unknown>;
          question = String(o.question ?? o.user_input ?? '');
          id = String(o.id ?? `q${n}`);
          const ref = o.reference ?? o.ground_truth;
          if (ref != null) reference = String(ref);
        } catch {
          /* plain line */
        }
      }
      if (question) items.push({ id, question, ...(reference != null ? { reference } : {}) });
    }
  }
  return items;
}

/** Optional sidecar written by `build_gold_set.py`. */
export function builderManifestPath(questionsPath: string): string {
  if (questionsPath.endsWith('.jsonl')) {
    return questionsPath.replace(/\.jsonl$/i, '.manifest.json');
  }
  return `${questionsPath}.manifest.json`;
}

export function loadBuilderManifestPath(questionsPath: string): string | null {
  const p = builderManifestPath(questionsPath);
  return existsSync(p) ? p : null;
}

export const PERMANENT_SKIP_IDS = ['gold_personalizeforce_34'] as const;
