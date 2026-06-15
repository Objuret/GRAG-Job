// RAGAS report visualizer.
//
// Consumes two file types and joins them by sample id:
//   * .report.json  -> per-sample metric scores + overall means (from ragas_eval.py)
//   * .jsonl        -> per-question runs with meta.n_chunks / meta.tokens /
//                      meta.elapsed_ms / meta.model (from ragas-export.ts)
//
// A "dataset" pairs the two files when they share a basename (e.g.
// `graph.report.json` + `graph.jsonl` -> single "graph" dataset). Either file
// alone is fine; missing run meta just yields blank cost/timing columns.
//
// No silent fallback: malformed files are rejected with a visible reason.
import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  RAGAS_EXPORTS_DIR,
  isRagasExportsFsAvailable,
  listRagasExports,
  readRagasExport,
} from './services/ragasExportsFs';

const METRIC_LABELS = {
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer relevancy',
  response_relevancy: 'Answer relevancy',
  context_recall: 'Context recall',
  context_precision: 'Context precision',
  llm_context_precision_with_reference: 'Context precision (LLM, w/ ref)',
  answer_correctness: 'Answer correctness',
};

const METRIC_ORDER = [
  'faithfulness',
  'answer_relevancy',
  'response_relevancy',
  'context_recall',
  'context_precision',
  'llm_context_precision_with_reference',
  'answer_correctness',
];

const REPORT_PALETTE = ['#b189ff', '#4cd99c', '#ffb454', '#5fd2ff', '#ff7fb3', '#e8c44a', '#6fddce', '#ff5d8a'];

// Published USD/1M-token rates at 2026-01. EDIT these if stale — exposed in the
// pricing panel so the user can override per run. No silent fallback: unknown
// models show "—" until you fill in a price.
const DEFAULT_MODEL_PRICING = {
  'claude-haiku-4-5':   { in: 1.00,  out: 5.00 },
  'claude-sonnet-4-5':  { in: 3.00,  out: 15.00 },
  'claude-sonnet-4-6':  { in: 3.00,  out: 15.00 },
  'claude-opus-4-6':    { in: 15.00, out: 75.00 },
  'claude-opus-4-7':    { in: 15.00, out: 75.00 },
  'gpt-4o-mini':        { in: 0.15,  out: 0.60 },
  'gpt-4o':             { in: 2.50,  out: 10.00 },
};

const labelOf = (metric) => METRIC_LABELS[metric] || metric;

function fmt(v, digits = 3) {
  if (v == null) return 'NA';
  if (typeof v !== 'number' || Number.isNaN(v)) return 'NA';
  return v.toFixed(digits);
}
function fmtInt(v) {
  if (v == null || Number.isNaN(v)) return '—';
  return Math.round(v).toLocaleString('en-US');
}
function fmtMs(v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (v < 1000) return `${Math.round(v)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}
function fmtCost(v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (v < 0.01) return `$${v.toFixed(4)}`;
  if (v < 1) return `$${v.toFixed(3)}`;
  return `$${v.toFixed(2)}`;
}

function heatColor(v) {
  if (v == null || Number.isNaN(v)) return 'transparent';
  if (v < 0.3) return 'rgba(255, 93, 138, 0.55)';
  if (v < 0.6) return 'rgba(255, 180, 84, 0.55)';
  if (v < 0.8) return 'rgba(95, 210, 255, 0.45)';
  return 'rgba(75, 224, 168, 0.55)';
}

function validateReport(obj) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
    throw new Error('top-level value is not a JSON object');
  }
  if (!Array.isArray(obj.per_sample)) throw new Error('missing "per_sample" array');
  if (!obj.overall || typeof obj.overall !== 'object') throw new Error('missing "overall" object');
  if (typeof obj.n_samples !== 'number' && typeof obj.n_rows !== 'number') {
    throw new Error('missing "n_samples" or "n_rows" number');
  }
  for (const row of obj.per_sample) {
    if (!row || typeof row !== 'object') throw new Error('per_sample contains a non-object entry');
    if (!('id' in row)) throw new Error('per_sample row missing "id"');
  }
}

function parseRunsFile(text) {
  const rows = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    let obj;
    try {
      obj = JSON.parse(line);
    } catch (e) {
      throw new Error(`line ${i + 1}: invalid JSON — ${e.message}`);
    }
    if (!obj || typeof obj !== 'object') {
      throw new Error(`line ${i + 1}: not an object`);
    }
    if (!('id' in obj)) {
      throw new Error(`line ${i + 1}: missing "id"`);
    }
    rows.push(obj);
  }
  if (!rows.length) throw new Error('no rows');
  return rows;
}

// Try to classify a dropped file as 'scores' (single JSON .report) or 'runs'
// (line-delimited JSONL). Prefer extension; fall back to content shape.
function classifyAndParse(file, text) {
  const lower = file.name.toLowerCase();
  if (lower.endsWith('.jsonl')) {
    return { kind: 'runs', payload: parseRunsFile(text) };
  }
  // .json or unknown — try report shape first
  try {
    const obj = JSON.parse(text);
    if (obj && typeof obj === 'object' && !Array.isArray(obj) && Array.isArray(obj.per_sample)) {
      validateReport(obj);
      return { kind: 'scores', payload: obj };
    }
  } catch (_) {
    // not a single JSON object — fall through to JSONL attempt
  }
  // Last resort: parse as JSONL
  return { kind: 'runs', payload: parseRunsFile(text) };
}

function scoresFromAtomicRows(rows) {
  const per_sample = rows.map((r) => ({
    id: r.id,
    ...(r.ragas && typeof r.ragas === 'object' ? r.ragas : {}),
    ...(r.deterministic && typeof r.deterministic === 'object' ? r.deterministic : {}),
    ...(r.score_meta?.skip_reason ? { skip_reason: r.score_meta.skip_reason } : {}),
  }));
  const overall = {};
  const overall_n = {};
  const metricKeys = new Set();
  for (const row of per_sample) {
    for (const k of Object.keys(row)) {
      if (k !== 'id' && k !== 'skip_reason') metricKeys.add(k);
    }
  }
  for (const k of metricKeys) {
    const vals = per_sample
      .map((row) => row[k])
      .filter((v) => typeof v === 'number' && !Number.isNaN(v));
    if (vals.length) {
      overall[k] = vals.reduce((a, b) => a + b, 0) / vals.length;
      overall_n[k] = vals.length;
    }
  }
  const n_scored = rows.filter((r) => r.score_meta?.scored).length;
  return {
    per_sample,
    overall,
    overall_n,
    n_samples: rows.length,
    n_rows: rows.length,
    n_scored,
  };
}

function basenameFor(file, kind) {
  let n = file.name;
  if (kind === 'scores') {
    n = n.replace(/\.report\.json$/i, '').replace(/\.json$/i, '');
  } else {
    n = n.replace(/\.scored\.jsonl$/i, '').replace(/\.jsonl$/i, '');
  }
  return n || file.name;
}

// Pull the run-level meta we visualize, from a JSONL row.
function runMetaOf(row) {
  const m = row?.meta || {};
  const t = m.tokens || {};
  const nChunks = typeof m.n_chunks_eval === 'number'
    ? m.n_chunks_eval
    : (typeof m.n_chunks === 'number' ? m.n_chunks : null);
  return {
    nChunks,
    nChunksRetrieved: typeof m.n_chunks_retrieved === 'number' ? m.n_chunks_retrieved : null,
    tokensIn: typeof t.answer_in === 'number' ? t.answer_in : null,
    tokensOut: typeof t.answer_out === 'number' ? t.answer_out : null,
    elapsedMs: typeof m.elapsed_ms === 'number' ? m.elapsed_ms : null,
    model: typeof m.model === 'string' ? m.model : null,
    error: m.error ?? null,
    skipReason: row?.score_meta?.skip_reason ?? null,
  };
}

function costOf({ tokensIn, tokensOut, model }, pricing) {
  if (!model || !pricing[model]) return null;
  const p = pricing[model];
  const inCost = tokensIn != null ? (tokensIn * p.in) / 1e6 : 0;
  const outCost = tokensOut != null ? (tokensOut * p.out) / 1e6 : 0;
  if (tokensIn == null && tokensOut == null) return null;
  return inCost + outCost;
}

/** Files the visualizer can ingest (excludes RunSpec `.ragas.json` configs). */
function isVisualizableExport(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith('.jsonl')) return true;
  if (lower.endsWith('.ragas.json')) return false;
  return lower.endsWith('.json');
}

function exportFileKind(name) {
  const lower = name.toLowerCase();
  if (lower.endsWith('.jsonl')) return 'runs';
  if (lower.endsWith('.report.json')) return 'scores';
  return 'json';
}

function fmtBytes(n) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtWhen(ms) {
  if (ms == null || Number.isNaN(ms)) return '—';
  return new Date(ms).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}

export default function RagasReportPage({ onBack }) {
  // Datasets: {id, name, color, scores: object|null, runs: array|null, runsByRowId: map}
  const [datasets, setDatasets] = useState([]);
  const [errors, setErrors] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [sortKey, setSortKey] = useState({ scope: 'id', metric: null, dir: 'asc' });
  const [pricing, setPricing] = useState(() => ({ ...DEFAULT_MODEL_PRICING }));
  const [showPricing, setShowPricing] = useState(false);
  const [exportsPicker, setExportsPicker] = useState(null);
  const [exportsPickerLoading, setExportsPickerLoading] = useState(false);
  const fileRef = useRef(null);
  const colorCursor = useRef(0);

  const mergeFile = useCallback((prev, file, kind, payload) => {
    const base = basenameFor(file, kind);
    const idx = prev.findIndex((d) => d.name === base);
    const atomicScores = kind === 'runs' && payload.some((r) => r?.ragas != null || r?.score_meta)
      ? scoresFromAtomicRows(payload)
      : null;
    if (idx >= 0) {
      const existing = prev[idx];
      const next = { ...existing };
      if (kind === 'scores') next.scores = payload;
      else {
        next.runs = payload;
        if (atomicScores && !next.scores) next.scores = atomicScores;
      }
      if (next.runs) next.runsByRowId = Object.fromEntries(next.runs.map((r) => [String(r.id), r]));
      const out = prev.slice();
      out[idx] = next;
      return out;
    }
    const color = REPORT_PALETTE[colorCursor.current % REPORT_PALETTE.length];
    colorCursor.current += 1;
    const created = {
      id: `${base}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: base,
      color,
      scores: kind === 'scores' ? payload : atomicScores,
      runs: kind === 'runs' ? payload : null,
      runsByRowId: kind === 'runs' ? Object.fromEntries(payload.map((r) => [String(r.id), r])) : {},
    };
    return [...prev, created];
  }, []);

  const ingestNamedText = useCallback((fileName, text) => {
    const fakeFile = { name: fileName };
    const { kind, payload } = classifyAndParse(fakeFile, text);
    setDatasets((prev) => mergeFile(prev, fakeFile, kind, payload));
  }, [mergeFile]);

  const handleFiles = useCallback(async (files) => {
    const errs = [];
    for (const f of files) {
      try {
        const text = await f.text();
        ingestNamedText(f.name, text);
      } catch (e) {
        errs.push(`${f.name}: ${e.message || String(e)}`);
      }
    }
    setErrors(errs);
  }, [ingestNamedText]);

  const openExportsPicker = useCallback(async () => {
    if (!isRagasExportsFsAvailable()) {
      setErrors([`${RAGAS_EXPORTS_DIR}/ is only available under npm run dev`]);
      return;
    }
    setExportsPickerLoading(true);
    try {
      const files = await listRagasExports();
      const wanted = files
        .filter((f) => isVisualizableExport(f.name))
        .sort((a, b) => a.name.localeCompare(b.name));
      if (!wanted.length) {
        setErrors([`No visualizable .json / .jsonl files in ${RAGAS_EXPORTS_DIR}/ yet`]);
        return;
      }
      setExportsPicker({ files: wanted, selected: new Set() });
      setErrors([]);
    } catch (e) {
      setErrors([`${RAGAS_EXPORTS_DIR}/: ${e.message || String(e)}`]);
    } finally {
      setExportsPickerLoading(false);
    }
  }, []);

  const loadSelectedExports = useCallback(async (names) => {
    if (!names.length) return;
    const errs = [];
    for (const name of names) {
      try {
        const text = await readRagasExport(name);
        ingestNamedText(name, text);
      } catch (e) {
        errs.push(`${name}: ${e.message || String(e)}`);
      }
    }
    setErrors(errs);
    setExportsPicker(null);
  }, [ingestNamedText]);

  const onPick = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) handleFiles(files);
    e.target.value = '';
  };
  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer?.files || []);
    if (files.length) handleFiles(files);
  }, [handleFiles]);

  const removeDataset = (id) => setDatasets((prev) => prev.filter((d) => d.id !== id));
  const renameDataset = (id, name) => setDatasets((prev) => prev.map((d) => (d.id === id ? { ...d, name } : d)));
  const clearAll = () => { setDatasets([]); setErrors([]); };

  const setPrice = (model, field, val) => {
    const n = Number(val);
    setPricing((cur) => ({
      ...cur,
      [model]: {
        in: field === 'in' ? (Number.isFinite(n) ? n : 0) : (cur[model]?.in ?? 0),
        out: field === 'out' ? (Number.isFinite(n) ? n : 0) : (cur[model]?.out ?? 0),
      },
    }));
  };

  const modelsInUse = useMemo(() => {
    const s = new Set();
    for (const d of datasets) {
      for (const r of d.runs || []) {
        const m = r?.meta?.model;
        if (typeof m === 'string') s.add(m);
      }
    }
    return Array.from(s).sort();
  }, [datasets]);

  const metricCols = useMemo(() => {
    const all = new Set();
    for (const d of datasets) {
      if (!d.scores) continue;
      for (const k of Object.keys(d.scores.overall || {})) all.add(k);
      for (const row of d.scores.per_sample || []) {
        for (const k of Object.keys(row)) if (k !== 'id') all.add(k);
      }
    }
    const arr = Array.from(all);
    arr.sort((a, b) => {
      const ia = METRIC_ORDER.indexOf(a);
      const ib = METRIC_ORDER.indexOf(b);
      if (ia >= 0 && ib >= 0) return ia - ib;
      if (ia >= 0) return -1;
      if (ib >= 0) return 1;
      return a.localeCompare(b);
    });
    return arr;
  }, [datasets]);

  const sampleRows = useMemo(() => {
    const rows = [];
    for (const d of datasets) {
      const runByIdRaw = d.runsByRowId || {};
      const seen = new Set();
      // Score rows first (left-join scores onto runs)
      for (const s of d.scores?.per_sample || []) {
        const sid = String(s.id);
        seen.add(sid);
        const run = runByIdRaw[sid] || null;
        const meta = run ? runMetaOf(run) : { nChunks: null, tokensIn: null, tokensOut: null, elapsedMs: null, model: null, error: null };
        rows.push({
          datasetId: d.id, datasetName: d.name, color: d.color,
          id: sid,
          scores: s,
          ...meta,
          cost: costOf(meta, pricing),
        });
      }
      // Runs that didn't get scored
      for (const r of d.runs || []) {
        const sid = String(r.id);
        if (seen.has(sid)) continue;
        const meta = runMetaOf(r);
        rows.push({
          datasetId: d.id, datasetName: d.name, color: d.color,
          id: sid,
          scores: null,
          ...meta,
          cost: costOf(meta, pricing),
        });
      }
    }
    if (sortKey.scope === 'metric' && sortKey.metric) {
      const m = sortKey.metric;
      const dir = sortKey.dir === 'asc' ? 1 : -1;
      rows.sort((a, b) => {
        const av = a.scores?.[m];
        const bv = b.scores?.[m];
        const aM = av == null || Number.isNaN(av);
        const bM = bv == null || Number.isNaN(bv);
        if (aM && bM) return 0;
        if (aM) return 1;
        if (bM) return -1;
        return (av - bv) * dir;
      });
    } else if (sortKey.scope === 'run' && sortKey.metric) {
      const field = sortKey.metric;
      const dir = sortKey.dir === 'asc' ? 1 : -1;
      rows.sort((a, b) => {
        const av = a[field], bv = b[field];
        const aM = av == null;
        const bM = bv == null;
        if (aM && bM) return 0;
        if (aM) return 1;
        if (bM) return -1;
        return (av - bv) * dir;
      });
    } else if (sortKey.scope === 'id') {
      const dir = sortKey.dir === 'asc' ? 1 : -1;
      rows.sort((a, b) => String(a.id).localeCompare(String(b.id)) * dir);
    } else if (sortKey.scope === 'dataset') {
      const dir = sortKey.dir === 'asc' ? 1 : -1;
      rows.sort((a, b) => a.datasetName.localeCompare(b.datasetName) * dir);
    }
    return rows;
  }, [datasets, sortKey, pricing]);

  const histograms = useMemo(() => {
    const out = {};
    for (const m of metricCols) {
      out[m] = datasets.filter((d) => d.scores).map((d) => {
        const buckets = new Array(10).fill(0);
        let nFinite = 0, nMissing = 0;
        for (const s of d.scores.per_sample || []) {
          const v = s[m];
          if (v == null || Number.isNaN(v) || typeof v !== 'number') { nMissing++; continue; }
          nFinite++;
          let idx = Math.floor(v * 10);
          if (idx > 9) idx = 9;
          if (idx < 0) idx = 0;
          buckets[idx]++;
        }
        return { datasetId: d.id, name: d.name, color: d.color, buckets, nFinite, nMissing };
      });
    }
    return out;
  }, [datasets, metricCols]);

  const runStats = useMemo(() => {
    return datasets.map((d) => {
      const runs = d.runs || [];
      let nOk = 0, nErr = 0;
      let sumChunks = 0, nChunksSeen = 0;
      let sumIn = 0, nInSeen = 0;
      let sumOut = 0, nOutSeen = 0;
      let sumMs = 0, nMsSeen = 0;
      let sumCost = 0, nCostSeen = 0, nCostMissing = 0;
      const modelSet = new Set();
      for (const r of runs) {
        const meta = runMetaOf(r);
        if (meta.error) nErr++; else nOk++;
        if (meta.nChunks != null) { sumChunks += meta.nChunks; nChunksSeen++; }
        if (meta.tokensIn != null) { sumIn += meta.tokensIn; nInSeen++; }
        if (meta.tokensOut != null) { sumOut += meta.tokensOut; nOutSeen++; }
        if (meta.elapsedMs != null) { sumMs += meta.elapsedMs; nMsSeen++; }
        if (meta.model) modelSet.add(meta.model);
        const c = costOf(meta, pricing);
        if (c != null) { sumCost += c; nCostSeen++; }
        else if (meta.tokensIn != null || meta.tokensOut != null) nCostMissing++;
      }
      return {
        datasetId: d.id, datasetName: d.name, color: d.color,
        hasRuns: runs.length > 0,
        nRuns: runs.length, nOk, nErr,
        models: Array.from(modelSet),
        chunks: { total: sumChunks, avg: nChunksSeen ? sumChunks / nChunksSeen : null, n: nChunksSeen },
        tokensIn: { total: sumIn, avg: nInSeen ? sumIn / nInSeen : null, n: nInSeen },
        tokensOut: { total: sumOut, avg: nOutSeen ? sumOut / nOutSeen : null, n: nOutSeen },
        elapsed: { total: sumMs, avg: nMsSeen ? sumMs / nMsSeen : null, n: nMsSeen },
        cost: { total: sumCost, avg: nCostSeen ? sumCost / nCostSeen : null, n: nCostSeen, missing: nCostMissing },
      };
    });
  }, [datasets, pricing]);

  const toggleSort = (scope, metric = null) => {
    setSortKey((cur) => {
      if (cur.scope === scope && cur.metric === metric) {
        return { ...cur, dir: cur.dir === 'asc' ? 'desc' : 'asc' };
      }
      return { scope, metric, dir: (scope === 'metric' || scope === 'run') ? 'desc' : 'asc' };
    });
  };

  const hasAny = datasets.length > 0;
  const hasAnyScores = datasets.some((d) => d.scores);
  const hasAnyRuns = datasets.some((d) => d.runs);

  return (
    <div className="ragas-page">
      <header className="ragas-page-header">
        <div className="ragas-page-brand">
          <button type="button" className="ragas-back" onClick={onBack} title="Back to workbench">
            ← Workbench
          </button>
          <div>
            <h1>RAGAS reports</h1>
            <p className="ragas-page-sub">
              Drop <code>.report.json</code> (scores from{' '}
              <code>ragas_eval.py</code>) and/or the matching <code>.jsonl</code>{' '}
              (per-run meta from <code>ragas-export.ts</code>) — same basename = same dataset.
            </p>
          </div>
        </div>
        <div className="ragas-page-actions">
          <input
            ref={fileRef}
            type="file"
            accept=".json,.jsonl,application/json,application/x-ndjson"
            multiple
            style={{ display: 'none' }}
            onChange={onPick}
          />
          {isRagasExportsFsAvailable() && (
            <button
              type="button"
              className="ragas-btn ragas-btn-primary"
              onClick={openExportsPicker}
              disabled={exportsPickerLoading}
            >
              {exportsPickerLoading ? 'Listing…' : `Browse ${RAGAS_EXPORTS_DIR}/`}
            </button>
          )}
          <button
            type="button"
            className={isRagasExportsFsAvailable() ? 'ragas-btn ragas-btn-ghost' : 'ragas-btn ragas-btn-primary'}
            onClick={() => fileRef.current?.click()}
          >
            Load other files…
          </button>
          {hasAnyRuns && (
            <button type="button" className="ragas-btn ragas-btn-ghost" onClick={() => setShowPricing((v) => !v)}>
              {showPricing ? 'Hide pricing' : 'Edit model pricing'}
            </button>
          )}
          {hasAny && (
            <button type="button" className="ragas-btn ragas-btn-ghost" onClick={clearAll}>
              Clear all
            </button>
          )}
        </div>
      </header>

      <main
        className={'ragas-page-body' + (dragOver ? ' drag-over' : '')}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        {errors.length > 0 && (
          <div className="ragas-errors" role="alert">
            <strong>Rejected {errors.length} file{errors.length === 1 ? '' : 's'}:</strong>
            <ul>{errors.map((m, i) => <li key={i}>{m}</li>)}</ul>
          </div>
        )}

        {exportsPicker && (
          <ExportsPickerModal
            files={exportsPicker.files}
            selected={exportsPicker.selected}
            onClose={() => setExportsPicker(null)}
            onChangeSelected={(selected) => setExportsPicker((cur) => (cur ? { ...cur, selected } : cur))}
            onLoad={(names) => loadSelectedExports(names)}
          />
        )}

        {!hasAny ? (
          <EmptyState onBrowse={isRagasExportsFsAvailable() ? openExportsPicker : null} />
        ) : (
          <>
            <DatasetsBar datasets={datasets} onRemove={removeDataset} onRename={renameDataset} />
            {showPricing && (
              <PricingPanel pricing={pricing} setPrice={setPrice} modelsInUse={modelsInUse} />
            )}
            {hasAnyRuns && (
              <Section
                title="Run cost & timing"
                hint={
                  <>
                    Per-dataset totals computed from the matched <code>.jsonl</code>.{' '}
                    Cost = (answer_in × in-price + answer_out × out-price) / 1e6.{' '}
                    <strong>Interpreter tokens are not tracked by the exporter</strong>,
                    so graph-arm cost is a lower bound on the answer step alone.
                  </>
                }
              >
                <RunStatsGrid stats={runStats} />
              </Section>
            )}
            {hasAnyScores && (
              <>
                <Section title="Overall mean by metric" hint="Bars compare the mean of each metric across loaded datasets. NA bars mean the metric was not scored (e.g. faithfulness on a zero-context row).">
                  <OverallChart datasets={datasets.filter((d) => d.scores)} metricCols={metricCols} />
                </Section>
                <Section title="Score distribution" hint="One histogram per metric. Each bar is the count of samples whose score falls in a 0.1-wide bucket; datasets are drawn side-by-side per bucket.">
                  <DistributionGrid metricCols={metricCols} histograms={histograms} />
                </Section>
              </>
            )}
            <Section
              title="Per-sample"
              hint="One row per sample × dataset. Scores are heat-coded; run columns come from the JSONL. Click any header to sort."
            >
              <PerSampleTable rows={sampleRows} metricCols={metricCols} sortKey={sortKey} onSort={toggleSort} />
            </Section>
          </>
        )}
      </main>
    </div>
  );
}

function ExportsPickerModal({ files, selected, onClose, onChangeSelected, onLoad }) {
  const toggle = (name) => {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onChangeSelected(next);
  };
  const selectAll = () => onChangeSelected(new Set(files.map((f) => f.name)));
  const selectNone = () => onChangeSelected(new Set());
  const selectedNames = Array.from(selected);

  return (
    <div className="ragas-picker-backdrop" role="presentation" onClick={onClose}>
      <div
        className="ragas-picker"
        role="dialog"
        aria-labelledby="ragas-picker-title"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="ragas-picker-head">
          <div>
            <h2 id="ragas-picker-title">Choose files from {RAGAS_EXPORTS_DIR}/</h2>
            <p className="ragas-picker-sub">
              Pick one or more <code>.report.json</code> (scores) and/or <code>.jsonl</code> (runs).
              RunSpec <code>.ragas.json</code> configs are hidden — they are not visualizable.
            </p>
          </div>
          <button type="button" className="ragas-report-remove" onClick={onClose} title="Close">✕</button>
        </header>
        <div className="ragas-picker-toolbar">
          <button type="button" className="ragas-btn ragas-btn-ghost" onClick={selectAll}>Select all</button>
          <button type="button" className="ragas-btn ragas-btn-ghost" onClick={selectNone}>Select none</button>
          <span className="ragas-picker-count">{selected.size} of {files.length} selected</span>
        </div>
        <ul className="ragas-picker-list">
          {files.map((f) => {
            const kind = exportFileKind(f.name);
            const checked = selected.has(f.name);
            return (
              <li key={f.name}>
                <label className={'ragas-picker-row' + (checked ? ' checked' : '')}>
                  <input type="checkbox" checked={checked} onChange={() => toggle(f.name)} />
                  <span className="ragas-picker-name mono">{f.name}</span>
                  <span className={'ragas-tag ' + (kind === 'runs' ? 'on' : kind === 'scores' ? 'on' : 'off')}>
                    {kind === 'runs' ? 'runs' : kind === 'scores' ? 'scores' : 'json'}
                  </span>
                  <span className="ragas-picker-meta">{fmtBytes(f.size)}</span>
                  <span className="ragas-picker-meta">{fmtWhen(f.mtimeMs)}</span>
                </label>
              </li>
            );
          })}
        </ul>
        <footer className="ragas-picker-foot">
          <button type="button" className="ragas-btn ragas-btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="ragas-btn ragas-btn-primary"
            disabled={!selected.size}
            onClick={() => onLoad(selectedNames)}
          >
            Load selected
          </button>
        </footer>
      </div>
    </div>
  );
}

function EmptyState({ onBrowse }) {
  return (
    <div className="ragas-empty">
      <div className="ragas-empty-icon">▤</div>
      <h2>No data loaded</h2>
      <p>
        {onBrowse ? (
          <>
            Exports from Run Builder live under <code>{RAGAS_EXPORTS_DIR}/</code> at the repo root —{' '}
            <button type="button" className="ragas-empty-link" onClick={onBrowse}>
              browse and pick files
            </button>
            , or drop files here.
          </>
        ) : (
          <>
            Drop one or more <code>.report.json</code> (scores) and/or{' '}
            <code>.jsonl</code> (per-run meta) files here, or use the loader above.
          </>
        )}
      </p>
      <p className="ragas-empty-hint">
        Files with the same basename get paired automatically (e.g.{' '}
        <code>graph.report.json</code> + <code>graph.jsonl</code> → one dataset
        called <code>graph</code>).
      </p>
    </div>
  );
}

function Section({ title, hint, children }) {
  return (
    <section className="ragas-section">
      <header>
        <h2>{title}</h2>
        {hint && <p className="ragas-section-hint">{hint}</p>}
      </header>
      <div className="ragas-section-body">{children}</div>
    </section>
  );
}

function DatasetsBar({ datasets, onRemove, onRename }) {
  return (
    <div className="ragas-reports-bar">
      {datasets.map((d) => {
        const hasScores = !!d.scores;
        const hasRuns = !!(d.runs && d.runs.length);
        return (
          <div key={d.id} className="ragas-report-chip" style={{ borderColor: d.color }}>
            <span className="ragas-report-swatch" style={{ background: d.color }} />
            <input
              className="ragas-report-name"
              value={d.name}
              onChange={(e) => onRename(d.id, e.target.value)}
              spellCheck={false}
              title="Rename (display only)"
            />
            <span className={'ragas-tag ' + (hasScores ? 'on' : 'off')} title="Scores from .report.json">
              scores{hasScores ? ` n=${d.scores.n_samples}` : ' —'}
            </span>
            <span className={'ragas-tag ' + (hasRuns ? 'on' : 'off')} title="Runs from .jsonl">
              runs{hasRuns ? ` n=${d.runs.length}` : ' —'}
            </span>
            <button type="button" className="ragas-report-remove" onClick={() => onRemove(d.id)} title="Remove">✕</button>
          </div>
        );
      })}
    </div>
  );
}

function PricingPanel({ pricing, setPrice, modelsInUse }) {
  if (!modelsInUse.length) {
    return (
      <div className="ragas-pricing">
        <div className="ragas-pricing-head">
          <strong>Model pricing</strong>
          <span className="ragas-pricing-sub">No models seen in the loaded runs yet.</span>
        </div>
      </div>
    );
  }
  return (
    <div className="ragas-pricing">
      <div className="ragas-pricing-head">
        <strong>Model pricing</strong>
        <span className="ragas-pricing-sub">
          USD per 1,000,000 tokens. Only models present in the loaded runs are shown.
          Known models are pre-filled with public list prices at 2026-01 — edit if stale; unknown models start at 0.
        </span>
      </div>
      <table className="ragas-pricing-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>$ / 1M input</th>
            <th>$ / 1M output</th>
          </tr>
        </thead>
        <tbody>
          {modelsInUse.map((m) => {
            const p = pricing[m] || { in: 0, out: 0 };
            return (
              <tr key={m}>
                <td className="mono">{m}</td>
                <td>
                  <input className="ragas-price-input"
                    type="number" step="0.01" min="0" value={p.in}
                    onChange={(e) => setPrice(m, 'in', e.target.value)} />
                </td>
                <td>
                  <input className="ragas-price-input"
                    type="number" step="0.01" min="0" value={p.out}
                    onChange={(e) => setPrice(m, 'out', e.target.value)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RunStatsGrid({ stats }) {
  return (
    <div className="ragas-runstats-grid">
      {stats.filter((s) => s.hasRuns).map((s) => (
        <div key={s.datasetId} className="ragas-runstats-card" style={{ borderTopColor: s.color }}>
          <div className="ragas-runstats-head">
            <span className="ragas-report-swatch" style={{ background: s.color }} />
            <strong>{s.datasetName}</strong>
            <span className="ragas-runstats-models">{s.models.join(', ') || '—'}</span>
          </div>
          <div className="ragas-runstats-tiles">
            <Tile label="Runs (ok / err)" big={`${s.nOk} / ${s.nErr}`} />
            <Tile label="Total chunks retrieved" big={fmtInt(s.chunks.total)} sub={s.chunks.avg != null ? `${s.chunks.avg.toFixed(1)} avg` : null} />
            <Tile label="Total tokens in" big={fmtInt(s.tokensIn.total)} sub={s.tokensIn.avg != null ? `${fmtInt(s.tokensIn.avg)} avg` : null} />
            <Tile label="Total tokens out" big={fmtInt(s.tokensOut.total)} sub={s.tokensOut.avg != null ? `${fmtInt(s.tokensOut.avg)} avg` : null} />
            <Tile label="Total query time" big={fmtMs(s.elapsed.total)} sub={s.elapsed.avg != null ? `${fmtMs(s.elapsed.avg)} avg` : null} />
            <Tile
              label="Estimated cost (USD)"
              big={fmtCost(s.cost.total)}
              sub={
                s.cost.missing > 0
                  ? `${s.cost.missing} rows missing price`
                  : (s.cost.avg != null ? `${fmtCost(s.cost.avg)} avg` : null)
              }
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function Tile({ label, big, sub }) {
  return (
    <div className="ragas-tile">
      <div className="ragas-tile-label">{label}</div>
      <div className="ragas-tile-big mono">{big}</div>
      {sub && <div className="ragas-tile-sub">{sub}</div>}
    </div>
  );
}

function OverallChart({ datasets, metricCols }) {
  if (!metricCols.length || !datasets.length) {
    return <div className="ragas-chart-empty">No score data loaded.</div>;
  }
  const rowHeight = 28;
  const gap = 8;
  const groupGap = 18;
  const labelWidth = 220;
  const valueWidth = 80;
  const barAreaWidth = 480;
  const groupHeight = (rowHeight * datasets.length) + (gap * (datasets.length - 1));
  const totalHeight = (groupHeight + groupGap) * metricCols.length;
  const svgWidth = labelWidth + barAreaWidth + valueWidth + 20;

  return (
    <div className="ragas-chart-wrap">
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${totalHeight}`} preserveAspectRatio="xMinYMin meet" role="img">
        {metricCols.map((m, mi) => {
          const yOff = mi * (groupHeight + groupGap);
          return (
            <g key={m} transform={`translate(0, ${yOff})`}>
              <text x={0} y={14} fontSize={12} fill="var(--text-main)" fontWeight="600">
                {labelOf(m)}
              </text>
              {[0, 0.25, 0.5, 0.75, 1.0].map((t) => (
                <line key={t}
                  x1={labelWidth + t * barAreaWidth} x2={labelWidth + t * barAreaWidth}
                  y1={20} y2={groupHeight}
                  stroke="var(--border)"
                  strokeDasharray={t === 0 || t === 1 ? 'none' : '2 3'} />
              ))}
              {datasets.map((d, di) => {
                const v = d.scores.overall?.[m];
                const n = d.scores.overall_n?.[m];
                const y = 20 + di * (rowHeight + gap);
                const hasVal = typeof v === 'number' && !Number.isNaN(v);
                const width = hasVal ? Math.max(2, v * barAreaWidth) : 0;
                return (
                  <g key={d.id} transform={`translate(0, ${y})`}>
                    <text x={labelWidth - 8} y={rowHeight / 2 + 4} textAnchor="end"
                          fontSize={11} fill="var(--text-muted)">
                      {d.name}
                    </text>
                    <rect x={labelWidth} y={0} width={barAreaWidth} height={rowHeight - 6}
                          fill="var(--bg-surface)" rx={3} />
                    {hasVal && (
                      <rect x={labelWidth} y={0} width={width} height={rowHeight - 6}
                            fill={d.color} rx={3} />
                    )}
                    <text x={labelWidth + barAreaWidth + 8} y={rowHeight / 2 + 4}
                          fontSize={11} fill="var(--text-main)">
                      {hasVal ? v.toFixed(3) : 'NA'}{n != null && hasVal ? `  (n=${n})` : ''}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function DistributionGrid({ metricCols, histograms }) {
  if (!metricCols.length) {
    return <div className="ragas-chart-empty">No metrics to distribute.</div>;
  }
  return (
    <div className="ragas-dist-grid">
      {metricCols.map((m) => (
        <Histogram key={m} metric={m} series={histograms[m] || []} />
      ))}
    </div>
  );
}

function Histogram({ metric, series }) {
  const buckets = 10;
  const maxCount = Math.max(1, ...series.flatMap((s) => s.buckets));
  const width = 360, height = 160, padTop = 18, padBot = 30, padLeft = 28, padRight = 8;
  const innerW = width - padLeft - padRight;
  const innerH = height - padTop - padBot;
  const bucketW = innerW / buckets;
  const subW = (bucketW - 4) / Math.max(1, series.length);

  return (
    <div className="ragas-hist">
      <div className="ragas-hist-head">
        <strong>{labelOf(metric)}</strong>
        <div className="ragas-hist-legend">
          {series.map((s) => (
            <span key={s.datasetId} className="ragas-hist-legend-item" title={`n=${s.nFinite} scored, ${s.nMissing} NA`}>
              <span className="ragas-report-swatch small" style={{ background: s.color }} />
              {s.name} <span className="dim">({s.nFinite})</span>
            </span>
          ))}
        </div>
      </div>
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMinYMin meet" role="img">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const y = padTop + innerH - t * innerH;
          return (
            <g key={t}>
              <line x1={padLeft} x2={width - padRight} y1={y} y2={y}
                    stroke="var(--border)" strokeDasharray={t === 0 ? 'none' : '2 3'} />
              <text x={padLeft - 4} y={y + 3} textAnchor="end" fontSize={9} fill="var(--text-dim)">
                {Math.round(t * maxCount)}
              </text>
            </g>
          );
        })}
        {Array.from({ length: buckets }, (_, i) => i).map((bi) => {
          const x0 = padLeft + bi * bucketW + 2;
          return (
            <g key={bi}>
              {series.map((s, si) => {
                const v = s.buckets[bi];
                const h = (v / maxCount) * innerH;
                const x = x0 + si * subW;
                return (
                  <rect key={s.datasetId}
                        x={x} y={padTop + innerH - h}
                        width={subW - 1} height={Math.max(0, h)}
                        fill={s.color} rx={1.5}>
                    <title>{`${s.name} · [${(bi/10).toFixed(1)}, ${((bi+1)/10).toFixed(1)}) → ${v}`}</title>
                  </rect>
                );
              })}
              {(bi === 0 || bi === buckets - 1 || bi === 5) && (
                <text x={x0 + bucketW / 2 - 2} y={padTop + innerH + 12}
                      textAnchor="middle" fontSize={9} fill="var(--text-dim)">
                  {(bi / 10).toFixed(1)}
                </text>
              )}
            </g>
          );
        })}
        <text x={padLeft + innerW / 2} y={height - 4} textAnchor="middle"
              fontSize={10} fill="var(--text-muted)">
          score bucket
        </text>
      </svg>
    </div>
  );
}

function PerSampleTable({ rows, metricCols, sortKey, onSort }) {
  if (!rows.length) {
    return <div className="ragas-chart-empty">No samples loaded.</div>;
  }
  const arrow = (scope, metric = null) => {
    if (sortKey.scope !== scope) return '';
    if ((scope === 'metric' || scope === 'run') && sortKey.metric !== metric) return '';
    return sortKey.dir === 'asc' ? ' ↑' : ' ↓';
  };
  return (
    <div className="ragas-table-wrap">
      <table className="ragas-table">
        <thead>
          <tr>
            <th className="sticky-col" onClick={() => onSort('dataset')}>Dataset{arrow('dataset')}</th>
            <th onClick={() => onSort('id')}>Sample id{arrow('id')}</th>
            {metricCols.map((m) => (
              <th key={m} className="th-score" onClick={() => onSort('metric', m)} title="Click to sort">
                {labelOf(m)}{arrow('metric', m)}
              </th>
            ))}
            <th className="th-run" onClick={() => onSort('run', 'nChunks')} title="Click to sort">Chunks{arrow('run', 'nChunks')}</th>
            <th className="th-run" onClick={() => onSort('run', 'tokensIn')}>Tokens in{arrow('run', 'tokensIn')}</th>
            <th className="th-run" onClick={() => onSort('run', 'tokensOut')}>Tokens out{arrow('run', 'tokensOut')}</th>
            <th className="th-run" onClick={() => onSort('run', 'elapsedMs')}>Elapsed{arrow('run', 'elapsedMs')}</th>
            <th className="th-run" onClick={() => onSort('run', 'cost')}>Cost{arrow('run', 'cost')}</th>
            <th className="th-run">Model</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.datasetId}_${r.id}_${i}`} title={r.error || ''} className={r.error ? 'row-err' : ''}>
              <td className="sticky-col">
                <span className="ragas-report-swatch small" style={{ background: r.color }} />
                <span>{r.datasetName}</span>
              </td>
              <td className="mono">{r.id}</td>
              {metricCols.map((m) => {
                const v = r.scores?.[m];
                const isNum = typeof v === 'number' && !Number.isNaN(v);
                return (
                  <td key={m} className="cell-score" style={{ background: heatColor(isNum ? v : null) }}>
                    <span className="mono">{fmt(v)}</span>
                  </td>
                );
              })}
              <td className="mono cell-run">{fmtInt(r.nChunks)}</td>
              <td className="mono cell-run">{fmtInt(r.tokensIn)}</td>
              <td className="mono cell-run">{fmtInt(r.tokensOut)}</td>
              <td className="mono cell-run">{fmtMs(r.elapsedMs)}</td>
              <td className="mono cell-run">{fmtCost(r.cost)}</td>
              <td className="mono cell-run">{r.model || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
