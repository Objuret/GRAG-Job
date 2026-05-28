/**
 * Dev-only bridge: read/write RAGAS artefacts under `<repo>/ragas_exports/`.
 * The local workbench has no backend; this keeps exports on disk next to the repo.
 */
import fs from 'node:fs';
import path from 'node:path';
import type { IncomingMessage, ServerResponse } from 'node:http';
import type { Connect, Plugin } from 'vite';

const API_PREFIX = '/__ragas_exports';

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    req.on('error', reject);
  });
}

function sendJson(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}

export function ragasExportsFs(repoRoot: string): Plugin {
  const exportsDir = path.join(repoRoot, 'ragas_exports');

  const ensureDir = () => {
    fs.mkdirSync(exportsDir, { recursive: true });
  };

  const safeFullPath = (rel: string): string => {
    const cleaned = String(rel || '')
      .replace(/\\/g, '/')
      .replace(/^\/+/, '')
      .replace(/\.\.(\/|$)/g, '');
    const full = path.resolve(exportsDir, cleaned);
    const relToRoot = path.relative(exportsDir, full);
    if (relToRoot.startsWith('..') || path.isAbsolute(relToRoot)) {
      throw new Error('path must stay inside ragas_exports');
    }
    return full;
  };

  const listFiles = (): { name: string; size: number; mtimeMs: number }[] => {
    ensureDir();
    const names = fs.readdirSync(exportsDir);
    return names
      .filter((n) => !n.startsWith('.'))
      .map((name) => {
        const st = fs.statSync(path.join(exportsDir, name));
        if (!st.isFile()) return null;
        return { name, size: st.size, mtimeMs: st.mtimeMs };
      })
      .filter(Boolean) as { name: string; size: number; mtimeMs: number }[];
  };

  const handler: Connect.NextHandleFunction = async (req, res, next) => {
    const url = req.url || '';
    if (!url.startsWith(API_PREFIX)) return next();

    try {
      ensureDir();
      const route = url.slice(API_PREFIX.length).split('?')[0];

      if (route === '/list' && req.method === 'GET') {
        sendJson(res, 200, { dir: 'ragas_exports', files: listFiles() });
        return;
      }

      if (route === '/read' && req.method === 'GET') {
        const q = new URL(url, 'http://local');
        const name = q.searchParams.get('name');
        if (!name) {
          sendJson(res, 400, { error: 'missing name' });
          return;
        }
        const full = safeFullPath(name);
        if (!fs.existsSync(full)) {
          sendJson(res, 404, { error: `not found: ${name}` });
          return;
        }
        const text = fs.readFileSync(full, 'utf-8');
        sendJson(res, 200, { name, text });
        return;
      }

      if (route === '/exists' && req.method === 'GET') {
        const q = new URL(url, 'http://local');
        const name = q.searchParams.get('name');
        if (!name) {
          sendJson(res, 400, { error: 'missing name' });
          return;
        }
        const full = safeFullPath(name);
        const exists = fs.existsSync(full) && fs.statSync(full).isFile();
        sendJson(res, 200, { exists, name });
        return;
      }

      if (route === '/write' && req.method === 'POST') {
        const raw = await readBody(req);
        let body: { name?: string; text?: string };
        try {
          body = JSON.parse(raw);
        } catch {
          sendJson(res, 400, { error: 'invalid JSON body' });
          return;
        }
        const name = body.name;
        const text = body.text;
        if (!name || typeof text !== 'string') {
          sendJson(res, 400, { error: 'name and text required' });
          return;
        }
        const full = safeFullPath(name);
        fs.mkdirSync(path.dirname(full), { recursive: true });
        fs.writeFileSync(full, text, 'utf-8');
        sendJson(res, 200, { ok: true, name, path: path.join('ragas_exports', name).replace(/\\/g, '/') });
        return;
      }

      sendJson(res, 404, { error: 'unknown route' });
    } catch (e) {
      sendJson(res, 500, { error: (e as Error).message });
    }
  };

  return {
    name: 'ragas-exports-fs',
    configureServer(server) {
      ensureDir();
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      ensureDir();
      server.middlewares.use(handler);
    },
  };
}
