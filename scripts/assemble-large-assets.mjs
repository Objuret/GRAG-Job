/**
 * Reassemble large binary assets that are committed as split <100 MB parts
 * (GitHub rejects any single file >100 MB on push).
 *
 * Each target is stored as `<name>.partNN` siblings; this concatenates them
 * back into `<name>`. Idempotent: skips a target whose reconstructed size
 * already matches the sum of its parts.
 *
 * Runs automatically via the frontend `postinstall` hook, and manually via
 * `npm run assets:assemble` from the repo root.
 */
import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, basename, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

const TARGETS = [
  'frontend/public/models/Xenova/e5-small-v2/onnx/model.onnx',
  'graph_export/grag_graph_latest.zip',
];

let rebuilt = 0;
for (const rel of TARGETS) {
  const out = join(REPO_ROOT, rel);
  const dir = dirname(out);
  const stem = basename(out);

  if (!existsSync(dir)) {
    console.warn(`assemble: missing dir for ${rel} — skipping`);
    continue;
  }
  const parts = readdirSync(dir)
    .filter((f) => f.startsWith(stem + '.part'))
    .sort();
  if (parts.length === 0) {
    console.warn(`assemble: no parts for ${rel} — skipping`);
    continue;
  }

  const partsBytes = parts.reduce((n, p) => n + statSync(join(dir, p)).size, 0);
  if (existsSync(out) && statSync(out).size === partsBytes) {
    continue; // already reconstructed
  }

  writeFileSync(out, Buffer.concat(parts.map((p) => readFileSync(join(dir, p)))));
  console.log(`assemble: rebuilt ${rel} from ${parts.length} parts (${partsBytes} bytes)`);
  rebuilt++;
}

if (rebuilt === 0) console.log('assemble: all large assets already in place');
