// Antigrav Workbench — main app (React + xyflow via ESM)
import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  ReactFlow, ReactFlowProvider, useNodesState, useEdgesState,
  addEdge, Background, Controls, MiniMap, Handle, Position, NodeResizer,
  BaseEdge, getBezierPath, EdgeLabelRenderer, useReactFlow, ConnectionMode, MarkerType,
} from '@xyflow/react';

// ─── Tweak defaults (persisted via __edit_mode_set_keys) ──────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "defaultTheme": "dark",
  "showMinimap": true,
  "animatedEdges": false,
  "accentColor": "#b189ff",
  "laneGap": 40,
  "defaultTopK": 50
}/*EDITMODE-END*/;

import {
  NODE_TYPES, QUERY_FRAGMENT_NODES, QUERY_FRAGMENT_CATALOG, QUERY_CONTAINER,
  PIPELINE_NODES, USAGE_NODES, MODULE_NODES, FACETS, DATASETS, PRESET_RESULTS, SAMPLE_CHUNKS,
  RUN_ROUTES, RUN_ANSWER_MODES, RUN_DATABASES, RUN_LEVERS,
} from './data/workbenchData';
import {
  DEFAULT_MODULE_HEADER,
  DEFAULT_MODULE_FOOTER,
  FRAGMENT_TEMPLATE_DEFAULTS,
  FRAGMENT_HUMAN_DEFAULTS,
  PLAN_INSERTS,
  DEMO_PLAN_PREVIEW,
  composeModuleCypher,
  composeHumanStory,
  extractPlanRefs,
  getFragmentTemplate,
  getFragmentHumanLine,
} from './query/queryModuleSyntax';
import { runUsageGraph, runRunSpec, compareRuns } from './services/pipeline';
import { MODELS, PROVIDERS, providerOf } from './data/models';
import { fetchDatasetStats } from './services/neo4j';
import RagasReportPage from './RagasReportPage.jsx';
import {
  RAGAS_EXPORTS_DIR,
  isRagasExportsFsAvailable,
  joinRagasExportPath,
  writeRagasExport,
} from './services/ragasExportsFs';

const RAGAS_SAVE_SUBDIR_KEY = 'ragas_exports_subdir';
const NT = Object.fromEntries([...NODE_TYPES, ...QUERY_FRAGMENT_NODES].map((n) => [n.id, n]));

const DONE_GRAPH_DATABASE = import.meta.env.VITE_NEO4J_DATABASE || 'herb-eval';
const DONE_GRAPH_RUN_ID = 'pilot_full_herb';

// ─── helpers ───────────────────────────────────────────────────────────────
const cls = (...xs) => xs.filter(Boolean).join(' ');
const uid = (p) => `${p}_${Math.random().toString(36).slice(2, 8)}`;

function isTypingTarget(el) {
  if (!el || !(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.isContentEditable) return true;
  return !!el.closest('[contenteditable="true"]');
}

function cloneSnap(nodes, edges) {
  return { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) };
}

function collectWithDescendants(nodes, seedIds) {
  const ids = new Set(seedIds);
  let added = true;
  while (added) {
    added = false;
    for (const n of nodes) {
      if (n.parentId && ids.has(n.parentId) && !ids.has(n.id)) {
        ids.add(n.id);
        added = true;
      }
    }
  }
  return ids;
}

function collectCopyNodes(nodes) {
  const sel = nodes.filter((n) => n.selected);
  if (!sel.length) return [];
  const ids = collectWithDescendants(nodes, sel.map((n) => n.id));
  return nodes.filter((n) => ids.has(n.id));
}

function snapClipboard(nodesSubset, allEdges) {
  const ids = new Set(nodesSubset.map((n) => n.id));
  const es = allEdges.filter((e) => ids.has(e.source) && ids.has(e.target));
  return {
    nodes: nodesSubset.map((n) => JSON.parse(JSON.stringify(n))),
    edges: es.map((e) => JSON.parse(JSON.stringify(e))),
  };
}

function remapPaste(nodes, edges) {
  const idMap = new Map();
  const pref = (t) => (t === 'stage' ? 'st' : t === 'lane' ? 'lane' : t === 'queryGroup' ? 'qg' : 'n');
  for (const n of nodes) idMap.set(n.id, uid(pref(n.type)));
  const newNodes = nodes.map((n) => ({
    ...n,
    id: idMap.get(n.id),
    parentId: n.parentId && idMap.has(n.parentId) ? idMap.get(n.parentId) : undefined,
    selected: false,
  }));
  const newEdges = edges.map((e) => ({
    ...e,
    id: `e_${idMap.get(e.source)}__${idMap.get(e.target)}`,
    source: idMap.get(e.source),
    target: idMap.get(e.target),
  }));
  return { newNodes, newEdges };
}

function offsetRoots(nodes, dx, dy) {
  const ids = new Set(nodes.map((n) => n.id));
  const roots = nodes.filter((n) => !n.parentId || !ids.has(n.parentId));
  const rootSet = new Set(roots.map((r) => r.id));
  return nodes.map((n) =>
    rootSet.has(n.id) ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } } : n
  );
}

/** Flow-space point inside some query module bounds (for parenting dropped fragments). */
function findQueryGroupAt(flowPos, nds) {
  for (const n of nds) {
    if (n.type !== 'queryGroup') continue;
    const w = Number(n.style?.width) || 560;
    const h = Number(n.style?.height) || 300;
    const { x, y } = n.position;
    if (flowPos.x >= x && flowPos.x <= x + w && flowPos.y >= y && flowPos.y <= y + h) return n;
  }
  return null;
}

const FRAGMENT_KINDS = new Set(QUERY_FRAGMENT_NODES.map((n) => n.id));
const Icon = ({ d, size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);
const I = {
  search:   <Icon d={<><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></>}/>,
  play:     <Icon d={<polygon points="6 4 20 12 6 20 6 4"/>}/>,
  zap:      <Icon d={<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>}/>,
  reset:    <Icon d={<><polyline points="1 4 1 10 7 10"/><path d="M3.5 15a9 9 0 1 0 2.4-9.5L1 10"/></>}/>,
  inspect:  <Icon d={<><circle cx="12" cy="12" r="3"/><path d="M2 12h4M18 12h4M12 2v4M12 18v4"/></>}/>,
  link:     <Icon d={<><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1-1"/></>}/>,
  close:    <Icon d={<><path d="M18 6L6 18M6 6l18 12"/></>}/>,
  layers:   <Icon d={<><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></>}/>,
  arrow:    <Icon d={<><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>}/>,
  prompt:   <Icon d={<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></>}/>,
  lock:     <Icon d={<><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>}/>,
  list:     <Icon d={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M8 9h2"/></>}/>,
};

const DEFAULT_FLOW_EDGE_OPTIONS = {
  type: 'default',
  markerEnd: { type: MarkerType.ArrowClosed, width: 13, height: 13, color: 'var(--neutral)' },
};

const FLOW_SIDES = ['top', 'right', 'bottom', 'left'];
const FLOW_SIDE_POS = [Position.Top, Position.Right, Position.Bottom, Position.Left];
const SIDE_TO_POS = Object.fromEntries(FLOW_SIDES.map((s, i) => [s, FLOW_SIDE_POS[i]]));

function portOffsetStyle(positionEnum, frac) {
  const pct = `${Math.round(Math.min(0.94, Math.max(0.06, frac)) * 100)}%`;
  if (positionEnum === Position.Top || positionEnum === Position.Bottom) return { left: pct };
  return { top: pct };
}

const FLOW_PORT_SPECS = Object.freeze(
  FLOW_SIDES.flatMap((side) => {
    const position = SIDE_TO_POS[side];
    return [
      { id: `h-${side}-a`, position, style: portOffsetStyle(position, 0.38) },
      { id: `h-${side}-b`, position, style: portOffsetStyle(position, 0.62) },
    ];
  }).sort((a, b) => a.id.localeCompare(b.id)),
);

function flowNodeConnectable(n) {
  return n?.type === 'stage' || n?.type === 'queryGroup' || n?.type === 'lane';
}

function FlowPorts() {
  return FLOW_PORT_SPECS.map((p) => (
    <Handle
      key={p.id}
      id={p.id}
      type="source"
      position={p.position}
      style={p.style}
      className="nodrag nopan"
      isConnectable
      isConnectableStart
      isConnectableEnd
    />
  ));
}

function mapEdgesForReactFlow(edgeList, animatedEdges) {
  const arrow = (err) =>
    err
      ? { type: MarkerType.ArrowClosed, width: 13, height: 13, color: 'var(--err)' }
      : { type: MarkerType.ArrowClosed, width: 13, height: 13, color: 'var(--neutral)' };
  return edgeList.map((e) => {
    const invalid = e.className === 'invalid' || e.data?.contractOk === false;
    const flowPulse = !!e.data?.flowPulse;
    return {
      ...e,
      animated: animatedEdges || flowPulse,
      className: cls(e.className, flowPulse && 'flow-pulse'),
      markerEnd: arrow(invalid),
    };
  });
}

function defaultFlowHandles(conn, nodeList) {
  const s = nodeList.find((n) => n.id === conn.source);
  const t = nodeList.find((n) => n.id === conn.target);
  let sourceHandle = conn.sourceHandle ?? null;
  let targetHandle = conn.targetHandle ?? null;
  if (flowNodeConnectable(s) && sourceHandle == null) sourceHandle = 'h-right-a';
  if (flowNodeConnectable(t) && targetHandle == null) targetHandle = 'h-left-a';
  return { ...conn, sourceHandle, targetHandle };
}

function connectionContractOk(conn, nodeList) {
  if (conn.source === conn.target) return false;
  const a = nodeList.find((n) => n.id === conn.source);
  const b = nodeList.find((n) => n.id === conn.target);
  return !!(a && b);
}

/** Stage ids that belong to a lane container (direct children only). */
function laneStageIds(nodes, laneId) {
  return new Set(nodes.filter((n) => n.type === 'stage' && n.parentId === laneId).map((n) => n.id));
}

/** Read width/height from React Flow `style` (number or `"123px"`) or return null. */
function readStyleLength(style, key) {
  if (!style || style[key] == null) return null;
  const v = style[key];
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function laneContentRect(lane) {
  const fromStyleW = readStyleLength(lane.style, 'width');
  const fromStyleH = readStyleLength(lane.style, 'height');
  const mw = lane.measured?.width;
  const mh = lane.measured?.height;
  const lw = fromStyleW ?? (Number.isFinite(mw) && mw > 0 ? mw : 600);
  const lh = fromStyleH ?? (Number.isFinite(mh) && mh > 0 ? mh : 220);
  return { lw, lh };
}

/** Prefer measured size; ignore 0×0 (xyflow before first measure). Fall back to explicit node dimensions then stage defaults. */
function stageBBoxSize(stage) {
  const mw = stage.measured?.width;
  const mh = stage.measured?.height;
  if (Number.isFinite(mw) && mw >= 12 && Number.isFinite(mh) && mh >= 12) return { w: mw, h: mh };
  const nw = stage.width;
  const nh = stage.height;
  if (Number.isFinite(nw) && nw >= 12 && Number.isFinite(nh) && nh >= 12) return { w: nw, h: nh };
  return { w: 184, h: 116 };
}

/**
 * True if this child stage should get `extent: 'parent'` when the lane is locked again.
 * Uses padded center-in-rect OR meaningful bbox overlap so resized lanes / measured sizes do not false-negative.
 */
function stageLockableInsideLane(stage, lane) {
  const { lw, lh } = laneContentRect(lane);
  const { w, h } = stageBBoxSize(stage);
  const { x, y } = stage.position;
  const pad = 16;
  const cx = x + w / 2;
  const cy = y + h / 2;
  const centerInside =
    cx >= -pad && cx <= lw + pad && cy >= -pad && cy <= lh + pad;

  const ix0 = Math.max(0, x);
  const iy0 = Math.max(0, y);
  const ix1 = Math.min(lw, x + w);
  const iy1 = Math.min(lh, y + h);
  const inter = Math.max(0, ix1 - ix0) * Math.max(0, iy1 - iy0);
  const area = Math.max(w * h, 1);
  const overlapFrac = inter / area;

  return centerInside || overlapFrac >= 0.22;
}

/**
 * Ordered list of stages inside a lane following internal edges (execution order).
 * Falls back to left-to-right sort if the subgraph is not a simple chain.
 */
function getLaneStageChainOrder(laneId, nodes, edges, idSet = null) {
  const ids = idSet ?? laneStageIds(nodes, laneId);
  if (!ids.size) return [];
  const internal = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  const targetOf = new Map(internal.map((e) => [e.source, e.target]));
  const hasIn = new Set(internal.map((e) => e.target));
  const heads = [...ids].filter((id) => !hasIn.has(id));
  if (heads.length === 1) {
    const order = [];
    let cur = heads[0];
    const guard = new Set();
    while (cur && !guard.has(cur)) {
      guard.add(cur);
      order.push(cur);
      cur = targetOf.get(cur);
    }
    if (order.length === ids.size) return order;
  }
  const byX = [...ids].sort((a, b) => {
    const na = nodes.find((n) => n.id === a);
    const nb = nodes.find((n) => n.id === b);
    return (na?.position?.x ?? 0) - (nb?.position?.x ?? 0);
  });
  return byX;
}

function externalInboundEdges(targetId, laneStageIdSet, edges) {
  return edges.filter(
    (e) => e.target === targetId && e.source !== targetId && !laneStageIdSet.has(e.source),
  );
}

function findEdgeBetween(edges, source, target) {
  return edges.find((e) => e.source === source && e.target === target);
}

// ─── Stage Node component (xyflow custom node) ─────────────────────────────
const StageNode = React.memo(({ id, data, selected }) => {
  const t = NT[data.kind];
  if (!t) return null;
  const phase = data.execPhase || 'idle';
  const cap = data.disabled
    ? 'unavailable'
    : phase === 'running'
      ? 'running'
      : phase === 'done'
        ? 'exec-done'
        : phase === 'failed'
          ? 'exec-failed'
          : 'runnable';
  const fragMeaning = data.kind?.startsWith('qf_')
    ? getFragmentHumanLine({ data }, data.kind)
    : null;
  const subDisplay = fragMeaning
    ? (fragMeaning.length > 90 ? `${fragMeaning.slice(0, 90)}…` : fragMeaning)
    : t.sub;
  const ringGradId = `execRing_${String(id ?? 'n').replace(/[^a-zA-Z0-9_-]/g, '_')}`;
  return (
    <div className={cls('node-stage', selected && 'selected', data.disabled && 'disabled', phase === 'running' && 'exec-running')}
         style={{ '--node-accent': t.color }}>
      {phase === 'running' && (
        <svg className="node-exec-ring" viewBox="0 0 184 124" preserveAspectRatio="none" aria-hidden>
          <defs>
            <linearGradient id={ringGradId} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--info)" stopOpacity="0.15" />
              <stop offset="50%" stopColor="var(--info)" stopOpacity="1" />
              <stop offset="100%" stopColor="var(--info)" stopOpacity="0.15" />
            </linearGradient>
          </defs>
          <rect
            x="2"
            y="2"
            width="180"
            height="120"
            rx="10"
            ry="10"
            fill="none"
            stroke={`url(#${ringGradId})`}
            strokeWidth="3"
            strokeLinecap="round"
            pathLength="100"
            strokeDasharray="18 320"
            className="node-exec-ring-stroke"
          />
        </svg>
      )}
      <div className="node-accent" />
      <FlowPorts />
      <div className="node-head">
        <div className="node-head-icon">{t.icon}</div>
        <div>
          <div className="node-title">{t.label}</div>
          <div className="node-subtitle" title={fragMeaning || undefined}>{subDisplay}</div>
        </div>
        {!['prompt', 'compare', 'qf_start', 'dataset', 'access', 'index', 'tags', 'facets'].includes(t.id) && (
          <div className={cls('node-toggle', !data.disabled && 'on')}
               onClick={(e) => { e.stopPropagation(); data.onToggle?.(); }} />
        )}
      </div>
      <div className="node-body">
        <div className="node-row">
          <span className="label">state</span>
          <span className="val">{data.disabled ? 'off' : phase}</span>
        </div>
        <div className="node-row">
          <span className="label">type</span>
          <span className="val">{(t.inType || '—')} → {(t.outType || '—')}</span>
        </div>
      </div>
      <div className="node-foot">
        <div className="io-pill in">
          {t.inType && <><span className="io-dot" style={{'--type-color': NT[Object.keys(NT).find(k => NT[k].outType === t.inType) || '']?.color || 'var(--neutral)'}}/>{t.inType}</>}
          {!t.inType && <span style={{color:'var(--text-dim)'}}>—</span>}
        </div>
        <span className={cls('cap-dot', cap)} />
        <div className="io-pill out">
          {t.outType && <>{t.outType}<span className="io-dot" style={{'--type-color': t.color}}/></>}
          {!t.outType && <span style={{color:'var(--text-dim)'}}>—</span>}
        </div>
      </div>
    </div>
  );
});

// ─── Lane (Group) Node ─────────────────────────────────────────────────────
const QueryGroupNode = React.memo(({ data, selected }) => (
  <>
    <NodeResizer minWidth={320} minHeight={200} isVisible={selected} />
    <div className={cls('node-query-group', selected && 'selected')}>
      <FlowPorts />
      <div className="query-group-head">
        <span className="query-group-icon">{QUERY_CONTAINER.icon}</span>
        <input className="query-group-title" defaultValue={data.label || 'Query module'}
               onPointerDown={(e) => e.stopPropagation()}
               onChange={(e) => data.onRename?.(e.target.value)} />
      </div>
      <div className="query-group-hint">Plan in · step order = query order · graph query out</div>
    </div>
  </>
));

const LaneNode = React.memo(({ data, selected }) => {
  return (
    <>
      <NodeResizer minWidth={600} minHeight={220} isVisible={selected} />
      <div className={cls('node-lane', selected && 'selected')}>
        <FlowPorts />
        <div className="lane-header">
          <input className="lane-name" defaultValue={data.label || 'Lane'}
                 onPointerDown={(e) => e.stopPropagation()}
                 onChange={(e) => data.onRename?.(e.target.value)} />
          <span className="lane-status">
            <span className={cls('cap-dot', data.running ? 'running' : 'runnable')} />
            {data.running ? 'running…' : (data.lastRun ? `${data.lastRun}ms` : 'ready')}
          </span>
          <div className="lane-actions">
            <button
              type="button"
              className={cls('lane-lock', data.lockContent !== false && 'is-on')}
              title={
                data.lockContent !== false
                  ? 'Locked: stages still inside the lane stay clamped — click to unlock'
                  : 'Unlocked: drag stages freely — click lock to clamp stages that overlap the lane interior'
              }
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => data.onSetLockContent?.(!(data.lockContent !== false))}
            >
              {I.lock}
            </button>
            <button type="button" className={cls('lane-run', data.running && 'running')}
                    disabled={data.running}
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={() => data.onRun?.()}>
              {I.play} {data.running ? 'Running' : 'Execute'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
});

const nodeTypes = { stage: StageNode, lane: LaneNode, queryGroup: QueryGroupNode };

// ─── Initial canvas: pipeline lane (top) + usage lane (bottom) ──────────────
const DEFAULT_USAGE_PARAMS = {
  prompt:            { mode: 'context' },
  interpret:         { model: '' },
  build_input:       {
    datasetId: DATASETS[0]?.id || 'Salesforce__HERB',
    maxChunks: 50,
    activeFacets: FACETS.map((f) => f.id),
    weightThreshold: 0,
    minRelevanceToFile: 0,
    groundingK: 10,
    minSim: 0.78,
    runId: DONE_GRAPH_RUN_ID,
  },
  ground:            {},
  retrieve_tags:     {},
  retrieve_baseline: {},
  answer:            { model: '' },
  compare:           {},
};

function buildInitial() {
  const xStart = 32, xGap = 232, yInner = 64;
  const nodeW = 184;
  const pipelineOrder = PIPELINE_NODES.map(n => n.id);
  const laneGap = 56;
  const pipeH = 244;

  const nodes = [];
  const edges = [];

  const mkEdge = (source, target) => {
    const conn = { source, target, sourceHandle: 'h-right-a', targetHandle: 'h-left-a' };
    const ok = connectionContractOk(conn, nodes);
    const sKind = nodes.find(n => n.id === source)?.data?.kind;
    const tKind = nodes.find(n => n.id === target)?.data?.kind;
    edges.push({
      id: `e_${source}__${target}`, ...conn, type: 'default', animated: false,
      className: ok ? undefined : 'invalid',
      data: { type: NT[sKind]?.outType, fromKind: sKind, toKind: tKind, contractOk: ok },
    });
  };

  // ── Pipeline lane: offline Python build — illustration only (not executed)
  const pipeW = xStart + (pipelineOrder.length - 1) * xGap + nodeW + 32;
  nodes.push({
    id: 'lane_pipeline', type: 'lane', position: { x: 0, y: 0 },
    style: { width: pipeW, height: pipeH, zIndex: -1 },
    data: { label: 'Pipeline — graph construction (offline, illustration)', lastRun: null, running: false, lockContent: true },
    draggable: true, selectable: true,
  });
  const pipeStages = pipelineOrder.map((kind, i) => ({
    id: `lane_pipeline_${kind}`, type: 'stage',
    position: { x: xStart + i * xGap, y: yInner },
    parentId: 'lane_pipeline', extent: 'parent',
    data: { kind, disabled: false, running: false },
  }));
  nodes.push(...pipeStages);
  for (let i = 0; i < pipeStages.length - 1; i++) mkEdge(pipeStages[i].id, pipeStages[i + 1].id);

  // ── Usage lane: the real executable fork/join DAG
  const usageY = pipeH + laneGap;
  const rowTop = yInner;
  const rowBot = yInner + 168;
  const usageH = rowBot + 116 + 28;
  // column index → x
  const cx = (col) => xStart + col * xGap;
  const U = (kind, col, row, idSuffix) => {
    const id = `lane_usage_${idSuffix || kind}`;
    nodes.push({
      id, type: 'stage',
      position: { x: cx(col), y: row },
      parentId: 'lane_usage', extent: 'parent',
      data: { kind, disabled: false, running: false, ...(DEFAULT_USAGE_PARAMS[kind] || {}) },
    });
    return id;
  };
  const usageW = cx(6) + nodeW + 32;
  nodes.push({
    id: 'lane_usage', type: 'lane', position: { x: 0, y: usageY },
    style: { width: usageW, height: usageH, zIndex: -1 },
    data: { label: 'Usage — live retrieval pipeline (executable)', lastRun: null, running: false, lockContent: true },
    draggable: true, selectable: true,
  });
  const midRow = Math.round((rowTop + rowBot) / 2);
  const nPrompt   = U('prompt', 0, midRow);
  const nInterp   = U('interpret', 1, midRow);
  const nBuild    = U('build_input', 2, midRow);
  const nGround   = U('ground', 3, rowTop);
  const nRetA     = U('retrieve_tags', 4, rowTop);
  const nAnsA     = U('answer', 5, rowTop, 'answer_a');
  const nRetB     = U('retrieve_baseline', 4, rowBot);
  const nAnsB     = U('answer', 5, rowBot, 'answer_b');
  const nCompare  = U('compare', 6, midRow);
  mkEdge(nPrompt, nInterp);
  mkEdge(nInterp, nBuild);
  mkEdge(nBuild, nGround);
  mkEdge(nBuild, nRetB);
  mkEdge(nGround, nRetA);
  mkEdge(nRetA, nAnsA);
  mkEdge(nRetB, nAnsB);
  mkEdge(nAnsA, nCompare);
  mkEdge(nAnsB, nCompare);

  // Empty Query module, seeded but not wired to the lanes — gives a clear starting surface
  // for fragment drops without making cross-lane wiring assumptions on first paint.
  const laneW = Math.max(pipeW, usageW);
  const qgW = 620;
  const qgH = 320;
  const qgX = Math.max(0, Math.round((laneW - qgW) / 2));
  const qgY = usageY + usageH + laneGap;
  nodes.push({
    id: 'query_module_initial',
    type: 'queryGroup',
    position: { x: qgX, y: qgY },
    style: { width: qgW, height: qgH, zIndex: 0 },
    data: {
      label: 'Query module',
      templateNote: '',
      headerCypher: DEFAULT_MODULE_HEADER,
      footerCypher: DEFAULT_MODULE_FOOTER,
      humanSummary: '',
    },
    draggable: true,
    selectable: true,
  });

  return { nodes, edges };
}

// ─── Fixed local graph/runtime config (override via Vite env only) ──────────
const envVar = (name) =>
  (typeof import.meta !== 'undefined' && import.meta.env?.[name]) || '';

const defaultConnConfig = {
  neo4jUri:       envVar('VITE_NEO4J_URI')      || 'neo4j://localhost:7687',
  neo4jUser:      envVar('VITE_NEO4J_USER')     || 'neo4j',
  neo4jPassword:  envVar('VITE_NEO4J_PASSWORD'),
  neo4jDatabase:  DONE_GRAPH_DATABASE,
  // Per-provider keys; each is whatever VITE_*_API_KEY is set, or '' if not.
  // The runtime resolves the right one from the model id via providerOf().
  keys: {
    openai:    envVar('VITE_OPENAI_API_KEY'),
    anthropic: envVar('VITE_ANTHROPIC_API_KEY'),
    deepseek:  envVar('VITE_DEEPSEEK_API_KEY'),
    ollama:    envVar('VITE_OLLAMA_API_KEY'),
    groq:      envVar('VITE_GROQ_API_KEY'),
  },
  model: envVar('VITE_MODEL') || 'deepseek-chat',
};

function normalizeConnConfig(cfg = {}) {
  return {
    ...defaultConnConfig,
    ...(cfg || {}),
    keys: { ...defaultConnConfig.keys, ...((cfg && cfg.keys) || {}) },
    neo4jDatabase: DONE_GRAPH_DATABASE,
  };
}

/** Map model ids → { provider → required-env-var }; missing keys → human msg.
 *  Used by both `runPipeline` and `runAllSpecs` so the precheck contract is
 *  identical: fail before issuing any network call. Loud on unknown model id
 *  (providerOf throws), surfaced through the same `missing` list. */
function missingProviderKeys(usedModels, keys) {
  const missing = [];
  const seenProviders = new Set();
  for (const m of usedModels) {
    let p;
    try { p = providerOf(m); } catch (e) { missing.push(e.message); continue; }
    if (seenProviders.has(p)) continue;
    seenProviders.add(p);
    if (!keys[p]) missing.push(`${PROVIDERS[p].label} (${PROVIDERS[p].envKeyVar})`);
  }
  return missing;
}

/** A Run is a config snapshot of the Usage graph; defaults mirror the node
 *  defaults in services/pipeline.ts so a fresh run reproduces the canvas. */
function makeDefaultRunSpec(connConfig, label, route = 'tags') {
  return {
    id: uid('spec'),
    label,
    database: DONE_GRAPH_DATABASE,
    route,
    moduleId: null,
    interpret: { model: connConfig.model, datasetId: null },
    buildInput: {
      maxChunks: 0, weightThreshold: 0, minRelevanceToFile: 0,
      groundingK: 0, minSim: 0.78,
      activeFacets: ['topic', 'entities', 'activity', 'temporal', 'evidence'],
      runId: DONE_GRAPH_RUN_ID,
    },
    answer: { model: connConfig.model, mode: 'context' },
    temperature: 0,
    sqlAgent: { maxToolCalls: 0, maxRowsPerQuery: 0, maxCellChars: 0 },
  };
}

/**
 * Translate a RunSpec into the JSON config consumed by
 * `ragas-export.ts --config`. Returns null for `route='module'`, which the
 * headless exporter does not (yet) reproduce — callers should refuse to
 * download in that case rather than silently downgrade.
 */
function specToRagasConfig(spec) {
  let mode;
  if (spec.route === 'tags') mode = 'graph';
  else if (spec.route === 'baseline' || spec.route === 'content') mode = 'baseline';
  else if (spec.route === 'sql_agent') mode = 'sql_agent';
  else return null; // 'module' or unknown
  return {
    $schema: 'ragas-runspec/v1',
    label: spec.label,
    route_origin: spec.route, // for traceability; the exporter uses `mode`
    mode,
    database: spec.database,
    model: spec.answer.model,
    interpreter_model: spec.interpret.model,
    prompt_mode: spec.answer.mode,
    dataset_id: spec.interpret.datasetId,
    temperature: spec.temperature,
    limit: spec.buildInput.maxChunks,
    grounding_k: spec.buildInput.groundingK,
    min_sim: spec.buildInput.minSim,
    min_w_chunk: spec.buildInput.weightThreshold,
    min_relevance_to_file: spec.buildInput.minRelevanceToFile,
    active_facets: spec.buildInput.activeFacets,
    exclude_sections: ['answerable_questions', 'unanswerable_questions', 'product_profile'],
    max_tool_calls: spec.sqlAgent?.maxToolCalls ?? 0,
    max_rows_per_query: spec.sqlAgent?.maxRowsPerQuery ?? 0,
    max_cell_chars: spec.sqlAgent?.maxCellChars ?? 0,
    answer_max_chunks: 200,
    answer_scrub: true,
  };
}

function downloadTextFile(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Write under `ragas_exports/` when the Vite dev bridge is up; else browser download. */
async function saveRagasArtifact(filename, text, saveSubdir) {
  const rel = joinRagasExportPath(saveSubdir, filename);
  if (isRagasExportsFsAvailable()) {
    const written = await writeRagasExport(rel, text);
    return written;
  }
  downloadTextFile(filename, text, 'application/octet-stream');
  return null;
}

async function exportRagasConfig(spec, saveSubdir, onStatus) {
  const cfg = specToRagasConfig(spec);
  if (!cfg) {
    alert(
      'Route "Query module" is not supported by the headless RAGAS exporter ' +
      '(composed Cypher has no batch pipeline). Switch route to Tags, Baseline, ' +
      'Content, or SQL agent before exporting, or run this spec interactively from the canvas.',
    );
    return;
  }
  const safe = (spec.label || 'run').replace(/[^a-zA-Z0-9._-]+/g, '_').replace(/^_+|_+$/g, '') || 'run';
  const filename = `${safe}.ragas.json`;
  const text = JSON.stringify(cfg, null, 2) + '\n';
  try {
    onStatus?.('Saving…');
    const path = await saveRagasArtifact(filename, text, saveSubdir);
    onStatus?.(path ? `Saved ${path}` : `Downloaded ${filename}`);
  } catch (e) {
    onStatus?.(`Export failed: ${e?.message || e}`);
  }
}

/** Read/write a dotted RunSpec path (`buildInput.minSim`) immutably. */
function specGet(spec, path) {
  return path.split('.').reduce((o, k) => (o == null ? o : o[k]), spec);
}
function specSet(spec, path, value) {
  const keys = path.split('.');
  const next = { ...spec };
  let cur = next;
  for (let i = 0; i < keys.length - 1; i++) {
    cur[keys[i]] = { ...cur[keys[i]] };
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return next;
}

/** A lever is inert when the chosen route doesn't consume it (greyed, not
 *  hidden — the user still sees the node owns it). */
function leverActive(field, route) {
  if (field.onlyRoute && !field.onlyRoute.includes(route)) return false;
  return true;
}
function groupActive(group, route) {
  if (group.onlyOnRoute && !group.onlyOnRoute.includes(route)) return false;
  return !(group.skipOnRoute && group.skipOnRoute.includes(route));
}

function toDatasetOptions(stats) {
  const rows = stats
    .filter((s) => s?.sourceId && !s.sourceId.endsWith('_demo') && s.fileCount > 0)
    .map((s) => ({
      id: s.sourceId,
      files: s.fileCount,
      chunks: s.chunkCount,
      tags: s.tagCount,
    }));
  return rows.length ? rows : DATASETS;
}



function makeLogEvent(runId, status, stage, message, meta = {}) {
  return {
    id: uid('log'),
    runId,
    status,
    stage,
    message,
    meta,
    at: new Date().toLocaleTimeString(),
  };
}

function makeHistoryEntry(runId, status, prompt, datasetId, durationMs, results, error = null) {
  const laneA = results?.lane_A;
  const laneB = results?.lane_B;
  return {
    id: runId,
    status,
    prompt,
    datasetId,
    durationMs,
    error,
    results,
    at: new Date().toLocaleString(),
    chunksA: laneA?.chunks ?? 0,
    chunksB: laneB?.chunks ?? 0,
    tokensIn: (laneA?.tokensIn ?? 0) + (laneB?.tokensIn ?? 0),
    tokensOut: (laneA?.tokensOut ?? 0) + (laneB?.tokensOut ?? 0),
  };
}

/** History entry for one Run Builder run (one config, one route). Carries the
 *  full RunSpec so the run is reproducible and RAGAS-exportable per-run. */
function makeRunHistoryEntry(runId, prompt, spec, result, error = null) {
  return {
    id: runId,
    kind: 'run',
    status: error ? 'failed' : 'ok',
    prompt,
    datasetId: spec.interpret.datasetId || null,
    durationMs: result?.durationMs ?? 0,
    error,
    spec,
    runResult: result || null,
    at: new Date().toLocaleString(),
    chunksA: result?.chunks ?? 0,
    chunksB: 0,
    tokensIn: result?.tokensIn ?? 0,
    tokensOut: result?.tokensOut ?? 0,
  };
}

// ─── App ───────────────────────────────────────────────────────────────────
function WorkbenchApp({ onOpenReports }) {
  const initial = useMemo(buildInitial, []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selected, setSelected] = useState(null);     // {kind:'node'|'lane', id}
  const [edgeSel, setEdgeSel]   = useState(null);     // edge id (drawer)
  const [tweaks, setTweak]      = useTweaks(TWEAK_DEFAULTS);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [theme, setTheme]       = useState(tweaks.defaultTheme);
  const [prompt, setPrompt]     = useState('Q2 revenue trends — what changed and why?');
  const rf = useReactFlow();
  const [results, setResults]   = useState({ lane_A: PRESET_RESULTS.full, lane_B: PRESET_RESULTS.baseline });
  const [outputView, setOutputView] = useState('llm');   // llm | chunks | table
  const [bottomTab, setBottomTab] = useState('comparison');
  const [bottomHeight, setBottomHeight] = useState(360);
  const connConfig = useMemo(() => normalizeConnConfig(), []);
  const [datasetOptions, setDatasetOptions] = useState(DATASETS);
  const [datasetLoadState, setDatasetLoadState] = useState({ loading: false, error: null, source: 'fallback' });
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineError, setPipelineError] = useState(null);
  const [runLog, setRunLog] = useState([
    makeLogEvent('initial', 'idle', 'workbench', 'Result console ready. Run the usage lane to populate live logs.'),
  ]);
  const [runHistory, setRunHistory] = useState([]);
  const [runSpecs, setRunSpecs] = useState(() => [
    makeDefaultRunSpec(connConfig, 'A · tags', 'tags'),
    makeDefaultRunSpec(connConfig, 'B · baseline', 'baseline'),
  ]);
  const [runResults, setRunResults] = useState([]);
  const [ragasSaveSubdir, setRagasSaveSubdir] = useState(() => {
    try { return localStorage.getItem(RAGAS_SAVE_SUBDIR_KEY) || ''; }
    catch { return ''; }
  });
  const [ragasExportStatus, setRagasExportStatus] = useState('');
  useEffect(() => {
    try { localStorage.setItem(RAGAS_SAVE_SUBDIR_KEY, ragasSaveSubdir); }
    catch { /* ignore */ }
  }, [ragasSaveSubdir]);
  const [runsBusy, setRunsBusy] = useState(false);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);
  useEffect(() => { document.documentElement.style.setProperty('--accent', tweaks.accentColor); }, [tweaks.accentColor]);
  // Tweaks-panel availability protocol
  useEffect(() => {
    const handler = (e) => {
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.type === '__activate_edit_mode')   setTweaksOpen(true);
      if (e.data.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', handler);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', handler);
  }, []);

  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  /** Keep refs aligned with render state so snapshots never lag one frame behind (fixes undo skipping the last edit). */
  nodesRef.current = nodes;
  edgesRef.current = edges;

  const edgesForReactFlow = useMemo(
    () => mapEdgesForReactFlow(edges, tweaks.animatedEdges),
    [edges, tweaks.animatedEdges],
  );

  const canvasRootRef = useRef(null);
  const clipboardRef = useRef(null);
  const runLaneAnimRef = useRef(0);
  const [, setUndoStack] = useState([]);
  const [, setRedoStack] = useState([]);

  const appendRunLog = useCallback((runId, status, stage, message, meta = {}) => {
    const event = makeLogEvent(runId, status, stage, message, meta);
    setRunLog((prev) => [...prev.slice(-199), event]);
  }, []);

  const recordRunHistory = useCallback((entry) => {
    setRunHistory((prev) => [entry, ...prev.filter((x) => x.id !== entry.id)].slice(0, 30));
  }, []);

  const restoreHistoryRun = useCallback((entry) => {
    if (entry?.kind === 'run') {
      if (!entry.runResult) return;
      setRunResults([entry.runResult]);
      if (entry.spec) setRunSpecs((s) => (s.some((x) => x.id === entry.spec.id) ? s : [...s, entry.spec]));
      setBottomTab('runs');
      appendRunLog(entry.id, 'restored', 'history', `Restored run "${entry.spec?.label}" into Run Builder.`);
      return;
    }
    if (!entry?.results) return;
    setResults(entry.results);
    setBottomTab('comparison');
    setOutputView('llm');
    appendRunLog(entry.id, 'restored', 'history', 'Restored run results into the comparison panel.');
  }, [appendRunLog]);

  const startBottomResize = useCallback((e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = bottomHeight;
    const onMove = (ev) => {
      const max = Math.max(240, Math.floor(window.innerHeight * 0.72));
      const next = Math.max(190, Math.min(max, startHeight + (startY - ev.clientY)));
      setBottomHeight(next);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [bottomHeight]);

  const commitBeforeChange = useCallback(() => {
    setUndoStack((u) => [...u.slice(-49), cloneSnap(nodesRef.current, edgesRef.current)]);
    setRedoStack([]);
  }, []);

  const undo = useCallback(() => {
    setUndoStack((u) => {
      if (!u.length) return u;
      const prev = u[u.length - 1];
      setRedoStack((r) => [...r, cloneSnap(nodesRef.current, edgesRef.current)]);
      setNodes(prev.nodes);
      setEdges(prev.edges);
      setSelected(null);
      setEdgeSel(null);
      return u.slice(0, -1);
    });
  }, [setNodes, setEdges]);

  const redo = useCallback(() => {
    setRedoStack((r) => {
      if (!r.length) return r;
      const next = r[r.length - 1];
      setUndoStack((u) => [...u.slice(-49), cloneSnap(nodesRef.current, edgesRef.current)]);
      setNodes(next.nodes);
      setEdges(next.edges);
      setSelected(null);
      setEdgeSel(null);
      return r.slice(0, -1);
    });
  }, [setNodes, setEdges]);

  const runLane = useCallback((laneId) => {
    runLaneAnimRef.current += 1;
    const token = runLaneAnimRef.current;
    const startedAt = Date.now();

    const schedule = (ms, fn) => {
      window.setTimeout(() => {
        if (token !== runLaneAnimRef.current) return;
        fn();
      }, ms);
    };

    const clearFlowPulse = () => {
      setEdges((eds) => eds.map((e) => ({ ...e, data: { ...e.data, flowPulse: false } })));
    };

    const finishLane = (lastRun) => {
      setNodes((nds) => nds.map((n) =>
        (n.id === laneId ? { ...n, data: { ...n.data, running: false, lastRun } } : n),
      ));
      clearFlowPulse();
    };

    const stages = laneStageIds(nodesRef.current, laneId);
    const order = getLaneStageChainOrder(laneId, nodesRef.current, edgesRef.current, stages);
    const D_EDGE = 360;
    const D_NODE = 520;
    const D_GAP = 160;

    if (!order.length) {
      setNodes((nds) => nds.map((n) => (n.id === laneId ? { ...n, data: { ...n.data, running: true } } : n)));
      schedule(700, () => finishLane(Date.now() - startedAt));
      return;
    }

    setNodes((nds) => nds.map((n) => {
      if (n.id === laneId) return { ...n, data: { ...n.data, running: true } };
      if (n.type === 'stage' && stages.has(n.id))
        return { ...n, data: { ...n.data, execPhase: 'idle' } };
      return n;
    }));
    clearFlowPulse();

    const setPulseEdgeIds = (edgeIds) => {
      const want = new Set(edgeIds);
      setEdges((eds) => eds.map((e) => ({ ...e, data: { ...e.data, flowPulse: want.has(e.id) } })));
    };

    const go = (i) => {
      if (token !== runLaneAnimRef.current) return;
      if (i >= order.length) {
        finishLane(Date.now() - startedAt);
        return;
      }

      const stageId = order[i];
      const prevId = i > 0 ? order[i - 1] : null;
      const pulseIds = [];
      if (prevId) {
        const e = findEdgeBetween(edgesRef.current, prevId, stageId);
        if (e) pulseIds.push(e.id);
      }
      for (const e of externalInboundEdges(stageId, stages, edgesRef.current)) {
        pulseIds.push(e.id);
      }
      setPulseEdgeIds(pulseIds);

      schedule(D_EDGE, () => {
        if (token !== runLaneAnimRef.current) return;
        clearFlowPulse();

        setNodes((nds) => nds.map((n) =>
          n.id === stageId && stages.has(n.id)
            ? { ...n, data: { ...n.data, execPhase: 'running' } }
            : n,
        ));

        schedule(D_NODE, () => {
          if (token !== runLaneAnimRef.current) return;
          setNodes((nds) => nds.map((n) =>
            n.id === stageId && stages.has(n.id)
              ? { ...n, data: { ...n.data, execPhase: 'done' } }
              : n,
          ));

          schedule(D_GAP, () => go(i + 1));
        });
      });
    };

    schedule(60, () => go(0));
  }, [setNodes, setEdges]);

  const patchNodeData = useCallback((id, dataPatch) => {
    setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...dataPatch } } : n)));
  }, [setNodes]);

  useEffect(() => {
    let live = true;
    const neo4jCfg = {
      uri: connConfig.neo4jUri,
      user: connConfig.neo4jUser,
      password: connConfig.neo4jPassword,
      database: DONE_GRAPH_DATABASE,
    };

    setDatasetLoadState({ loading: true, error: null, source: 'graph' });
    fetchDatasetStats(neo4jCfg, DONE_GRAPH_RUN_ID)
      .then((stats) => {
        if (!live) return;
        setDatasetOptions(toDatasetOptions(stats));
        setDatasetLoadState({ loading: false, error: null, source: stats.length ? 'graph' : 'fallback' });
      })
      .catch((err) => {
        if (!live) return;
        setDatasetOptions(DATASETS);
        setDatasetLoadState({ loading: false, error: err?.message || String(err), source: 'fallback' });
      });

    return () => { live = false; };
  }, [connConfig.neo4jUri, connConfig.neo4jUser, connConfig.neo4jPassword]);

  const setUsageLaneState = useCallback((patch, stagePhase) => {
    setNodes((nds) => nds.map((n) => {
      if (n.id === 'lane_usage' && n.type === 'lane')
        return { ...n, data: { ...n.data, ...patch } };
      if (stagePhase && n.type === 'stage' && n.parentId === 'lane_usage')
        return { ...n, data: { ...n.data, execPhase: stagePhase } };
      return n;
    }));
  }, [setNodes]);

  const runPipeline = useCallback(async () => {
    const runId = uid('run');
    const t0 = Date.now();
    const liveNodes = nodesRef.current;
    const usageStages = liveNodes.filter(
      (n) => n.type === 'stage' && n.parentId === 'lane_usage' && !n.data?.disabled,
    );
    // Models that the wired nodes will actually call, so the key precheck
    // can't pass here and then fail late inside a service call.
    const usedModels = usageStages
      .filter((n) => n.data?.kind === 'interpret' || n.data?.kind === 'answer')
      .map((n) => n.data?.model || connConfig.model);
    const buildNode = usageStages.find((n) => n.data?.kind === 'build_input');
    const datasetGuess = buildNode?.data?.datasetId || null;
    appendRunLog(runId, 'running', 'start', `Pipeline queued (${usageStages.length} nodes).`, { prompt });
    const missing = missingProviderKeys(usedModels, connConfig.keys);
    if (missing.length) {
      const message = `API key/model error: ${missing.join('; ')}.`;
      setPipelineError(message);
      appendRunLog(runId, 'failed', 'config', message);
      recordRunHistory(makeHistoryEntry(runId, 'failed', prompt, datasetGuess, Date.now() - t0, null, message));
      return;
    }
    setPipelineRunning(true);
    setPipelineError(null);
    setUsageLaneState({ running: true, lastRun: null }, 'running');
    try {
      const env = {
        prompt,
        connConfig: { model: connConfig.model, keys: connConfig.keys },
        neo4jCfg: {
          uri: connConfig.neo4jUri,
          user: connConfig.neo4jUser,
          password: connConfig.neo4jPassword,
          database: DONE_GRAPH_DATABASE,
        },
        runId,
        nodes: liveNodes,
        edges: edgesRef.current,
        log: (stage, status, message) => appendRunLog(runId, status, stage, message),
      };
      const { results } = await runUsageGraph(liveNodes, edgesRef.current, 'lane_usage', env);
      const elapsed = Date.now() - t0;
      setResults(results);
      appendRunLog(runId, 'ok', 'finish', `Run finished in ${elapsed}ms.`);
      recordRunHistory(makeHistoryEntry(runId, 'ok', prompt, datasetGuess, elapsed, results));
      setUsageLaneState({ running: false, lastRun: elapsed }, 'done');
    } catch (err) {
      const message = err?.message || String(err);
      setPipelineError(message);
      appendRunLog(runId, 'failed', 'error', message);
      recordRunHistory(makeHistoryEntry(runId, 'failed', prompt, datasetGuess, Date.now() - t0, null, message));
      setUsageLaneState({ running: false, lastRun: null }, 'failed');
    } finally {
      setPipelineRunning(false);
    }
  }, [prompt, connConfig, appendRunLog, recordRunHistory, setUsageLaneState]);

  // Run Builder: execute every configured Run on the shared prompt, in order,
  // and surface them side by side. One run's failure is reported loudly (in
  // its result card + history + log) and does not abort the others.
  const runAllSpecs = useCallback(async () => {
    if (!runSpecs.length || runsBusy) return;
    const liveNodes = nodesRef.current;
    const baseEnv = {
      prompt,
      connConfig: { model: connConfig.model, keys: connConfig.keys },
      neo4jCfg: {
        uri: connConfig.neo4jUri,
        user: connConfig.neo4jUser,
        password: connConfig.neo4jPassword,
        database: DONE_GRAPH_DATABASE,
      },
      nodes: liveNodes,
      edges: edgesRef.current,
    };
    // Key precheck across every model any run will call — fail before issuing
    // network calls, same contract as runPipeline.
    const usedModels = runSpecs.flatMap((s) => [s.interpret.model, s.answer.model]);
    const missing = missingProviderKeys(usedModels, connConfig.keys);
    if (missing.length) {
      const message = `API key/model error: ${missing.join('; ')}.`;
      setPipelineError(message);
      appendRunLog('runs', 'failed', 'config', message);
      return;
    }
    setRunsBusy(true);
    setPipelineError(null);
    setBottomTab('runs');
    const collected = [];
    for (const spec of runSpecs) {
      const runId = uid('run');
      const t0 = Date.now();
      appendRunLog(runId, 'running', 'run', `Run "${spec.label}" queued (${spec.route}, db=${spec.database}).`, { prompt });
      const env = { ...baseEnv, runId, log: (stage, status, message) => appendRunLog(runId, status, stage, message) };
      try {
        const result = await runRunSpec(spec, env);
        collected.push(result);
        setRunResults(collected.slice());
        appendRunLog(runId, 'ok', 'run', `Run "${spec.label}" finished in ${result.durationMs}ms.`);
        recordRunHistory(makeRunHistoryEntry(runId, prompt, spec, result));
      } catch (err) {
        const message = err?.message || String(err);
        const failed = {
          specId: spec.id, label: spec.label, route: spec.route, database: spec.database,
          error: message, response: '', chunks: 0, tokensIn: 0, tokensOut: 0,
          durationMs: Date.now() - t0, plan: null, retrievalInput: null,
          retrievedChunks: [], topFacets: [], metrics: null,
        };
        collected.push(failed);
        setRunResults(collected.slice());
        appendRunLog(runId, 'failed', 'run', `Run "${spec.label}": ${message}`);
        recordRunHistory(makeRunHistoryEntry(runId, prompt, spec, null, message));
      }
    }
    setRunsBusy(false);
  }, [runSpecs, runsBusy, prompt, connConfig, appendRunLog, recordRunHistory]);

  const runLaneWithActualWork = useCallback((laneId) => {
    // The usage lane runs the real services pipeline, so its node status is
    // driven by runPipeline itself (below) — not by the cosmetic stage
    // animation, which would otherwise report a success/duration unrelated to
    // the actual run. Other lanes have no live execution and keep the
    // illustrative animation.
    if (laneId === 'lane_usage') { runPipeline(); return; }
    runLane(laneId);
  }, [runLane, runPipeline]);

  // Wire callbacks into nodes (toggle, rename, run, etc.)
  const wiredNodes = useMemo(() => nodes.map((n) => {
    if (n.type === 'lane') {
      return { ...n, data: { ...n.data,
        onRename: (v) => setNodes((nds) => nds.map((x) => (x.id === n.id ? { ...x, data: { ...x.data, label: v } } : x))),
        onRun: () => runLaneWithActualWork(n.id),
        onSetLockContent: (lock) => {
          commitBeforeChange();
          setNodes((nds) => {
            const laneNode = nds.find((z) => z.id === n.id && z.type === 'lane');
            return nds.map((x) => {
              if (x.id === n.id && x.type === 'lane')
                return { ...x, data: { ...x.data, lockContent: lock } };
              if (x.parentId === n.id && x.type === 'stage') {
                const { extent: _ignore, ...rest } = x;
                if (!lock) return rest;
                if (laneNode && stageLockableInsideLane(x, laneNode))
                  return { ...rest, extent: 'parent' };
                return rest;
              }
              return x;
            });
          });
        },
      } };
    }
    if (n.type === 'queryGroup') {
      return { ...n, data: { ...n.data,
        onRename: (v) => setNodes((nds) => nds.map((x) => (x.id === n.id ? { ...x, data: { ...x.data, label: v } } : x))),
      } };
    }
    if (n.type === 'stage') {
      return { ...n, data: { ...n.data,
        onToggle: () => setNodes((nds) => nds.map((x) => (x.id === n.id ? { ...x, data: { ...x.data, disabled: !x.data.disabled } } : x))),
      } };
    }
    return n;
  }), [nodes, runLaneWithActualWork, setNodes, commitBeforeChange]);

  const onConnect = useCallback((c) => {
    commitBeforeChange();
    const conn = defaultFlowHandles(c, nodes);
    const s = nodes.find((n) => n.id === conn.source);
    const t = nodes.find((n) => n.id === conn.target);
    const contractOk = connectionContractOk(conn, nodes);
    let data = { type: '', fromKind: '', toKind: '', contractOk };
    if (t?.type === 'queryGroup' && s?.type === 'stage') {
      data = { type: s?.data?.kind ? (NT[s.data.kind]?.outType ?? '') : '', fromKind: s?.data?.kind ?? '', toKind: 'queryGroup', contractOk };
    } else if (s?.type === 'queryGroup' && t?.type === 'stage') {
      data = { type: QUERY_CONTAINER.outType, fromKind: 'queryGroup', toKind: t?.data?.kind ?? '', contractOk };
    } else if (s?.type === 'stage' && t?.type === 'stage') {
      const sKind = NT[s.data.kind], tKind = NT[t.data.kind];
      if (s.data?.kind === 'facets' && t.data?.kind === 'graphquery') {
        data = { type: 'graph_scope', fromKind: 'facets', toKind: 'graphquery', contractOk };
      } else {
        data = { type: sKind?.outType ?? '', fromKind: s.data.kind, toKind: t.data.kind, contractOk };
      }
    }
    setEdges((eds) =>
      addEdge(
        {
          ...conn,
          type: 'default',
          animated: false,
          className: contractOk ? undefined : 'invalid',
          data,
        },
        eds,
      ),
    );
  }, [commitBeforeChange, setEdges, nodes]);

  /** Checkpoint before a drag mutates positions (onNodesChange does not go through commitBeforeChange). */
  const onNodeDragStart = useCallback(() => {
    commitBeforeChange();
  }, [commitBeforeChange]);

  const isValidConnection = useCallback(({ source, target }) => source !== target, []);

  const onSelectionChange = useCallback(({ nodes: ns, edges: es }) => {
    if (es.length === 1) { setEdgeSel(es[0].id); setSelected(null); return; }
    setEdgeSel(null);
    if (ns.length === 1) setSelected({ kind: ns[0].type, id: ns[0].id });
    else setSelected(null);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    const kind = e.dataTransfer.getData('application/ag-kind');
    if (!kind) return;
    commitBeforeChange();
    const flowPos = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });

    if (kind === 'queryContainer') {
      const gid = uid('qg');
      const gw = 560;
      const gh = 300;
      const pos = { x: flowPos.x - gw / 2, y: flowPos.y - gh / 2 };
      setNodes((nds) => nds.concat(
        {
          id: gid,
          type: 'queryGroup',
          position: pos,
          style: { width: gw, height: gh, zIndex: 0 },
          data: {
            label: 'Query module',
            templateNote: '',
            headerCypher: DEFAULT_MODULE_HEADER,
            footerCypher: DEFAULT_MODULE_FOOTER,
            humanSummary: '',
          },
          draggable: true,
          selectable: true,
        },
        {
          id: uid('qf'),
          type: 'stage',
          parentId: gid,
          extent: 'parent',
          position: { x: 28, y: 72 },
          data: {
            kind: 'qf_start',
            disabled: false,
            running: false,
            cypherTemplate: FRAGMENT_TEMPLATE_DEFAULTS.qf_start,
          },
          draggable: true,
          selectable: true,
        },
      ));
      return;
    }

    if (FRAGMENT_KINDS.has(kind) && kind !== 'qf_start') {
      setNodes((nds) => {
        const parent = findQueryGroupAt(flowPos, nds);
        if (!parent) return nds;
        const w = 184;
        const h = 116;
        const rel = {
          x: flowPos.x - parent.position.x - w / 2,
          y: flowPos.y - parent.position.y - h / 2,
        };
        return nds.concat({
          id: uid(kind),
          type: 'stage',
          parentId: parent.id,
          extent: 'parent',
          position: rel,
          data: {
            kind,
            disabled: false,
            running: false,
            cypherTemplate: FRAGMENT_TEMPLATE_DEFAULTS[kind] ?? '',
          },
          draggable: true,
          selectable: true,
        });
      });
      return;
    }

    const isLane = kind === 'lane';
    const w = isLane ? 720 : 184;
    const h = isLane ? 240 : 116;
    const pos = { x: flowPos.x - w / 2, y: flowPos.y - h / 2 };
    if (isLane) {
      setNodes((nds) => nds.concat({
        id: uid('lane'), type: 'lane', position: pos,
        style: { width: w, height: h, zIndex: -1 },
        data: { label: 'New Lane', lastRun: null, running: false, lockContent: true },
      }));
    } else {
      setNodes((nds) => nds.concat({
        id: uid(kind), type: 'stage', position: pos,
        data: { kind, disabled: false, running: false },
      }));
    }
  }, [commitBeforeChange, setNodes, rf]);

  const copySelection = useCallback(() => {
    const ns = collectCopyNodes(nodesRef.current);
    if (!ns.length) return;
    clipboardRef.current = snapClipboard(ns, edgesRef.current);
  }, []);

  const pasteFromClipboard = useCallback(() => {
    const clip = clipboardRef.current;
    if (!clip?.nodes?.length) return;
    commitBeforeChange();
    let { newNodes, newEdges } = remapPaste(clip.nodes, clip.edges);
    newNodes = offsetRoots(newNodes, 40, 40);
    setNodes((nds) => [...nds.map((n) => ({ ...n, selected: false })), ...newNodes.map((n) => ({ ...n, selected: true }))]);
    setEdges((eds) => [...eds, ...newEdges]);
  }, [commitBeforeChange, setNodes, setEdges]);

  const duplicateSelection = useCallback(() => {
    const ns = collectCopyNodes(nodesRef.current);
    if (!ns.length) return;
    const clip = snapClipboard(ns, edgesRef.current);
    commitBeforeChange();
    let { newNodes, newEdges } = remapPaste(clip.nodes, clip.edges);
    newNodes = offsetRoots(newNodes, 24, 24);
    setNodes((nds) => [...nds.map((n) => ({ ...n, selected: false })), ...newNodes.map((n) => ({ ...n, selected: true }))]);
    setEdges((eds) => [...eds, ...newEdges]);
  }, [commitBeforeChange, setNodes, setEdges]);

  const selectAllOnCanvas = useCallback(() => {
    setNodes((nds) => nds.map((n) => ({ ...n, selected: true })));
    setEdges((eds) => eds.map((e) => ({ ...e, selected: true })));
    setSelected(null);
    setEdgeSel(null);
  }, [setNodes, setEdges, setSelected, setEdgeSel]);

  const clearCanvasSelection = useCallback(() => {
    setNodes((nds) => nds.map((n) => (n.selected ? { ...n, selected: false } : n)));
    setEdges((eds) => eds.map((e) => (e.selected ? { ...e, selected: false } : e)));
    setSelected(null);
    setEdgeSel(null);
  }, [setNodes, setEdges, setSelected, setEdgeSel]);

  const deleteSelection = useCallback(() => {
    const nds = nodesRef.current;
    const eds = edgesRef.current;
    const selectedE = eds.filter((e) => e.selected);
    if (selectedE.length) {
      commitBeforeChange();
      const rm = new Set(selectedE.map((e) => e.id));
      setEdges((e) => e.filter((x) => !rm.has(x.id)));
      setEdgeSel(null);
      return;
    }
    if (edgeSel) {
      commitBeforeChange();
      setEdges((e) => e.filter((x) => x.id !== edgeSel));
      setEdgeSel(null);
      return;
    }
    const sel = nds.filter((n) => n.selected);
    const ids = collectWithDescendants(nds, sel.map((n) => n.id));
    if (!ids.size) return;
    commitBeforeChange();
    setNodes((n) => n.filter((x) => !ids.has(x.id)));
    setEdges((e) => e.filter((x) => !ids.has(x.source) && !ids.has(x.target)));
    setSelected(null);
    setEdgeSel(null);
  }, [commitBeforeChange, edgeSel, setNodes, setEdges]);

  const runCanvasSelection = useCallback(() => {
    const nds = nodesRef.current;
    const sel = nds.filter((n) => n.selected);
    if (!sel.length) {
      runLaneWithActualWork('lane_pipeline');
      runLaneWithActualWork('lane_usage');
      return;
    }
    const lanes = new Set();
    for (const n of sel) {
      if (n.type === 'lane') lanes.add(n.id);
      else if (n.parentId) {
        const p = nds.find((x) => x.id === n.parentId);
        if (p?.type === 'lane') lanes.add(n.parentId);
      }
    }
    lanes.forEach((id) => runLaneWithActualWork(id));
  }, [runLaneWithActualWork]);

  const runAll = useCallback(() => {
    runLaneWithActualWork('lane_pipeline');
    runLaneWithActualWork('lane_usage');
  }, [runLaneWithActualWork]);

  const focusCanvas = useCallback(() => {
    canvasRootRef.current?.focus({ preventScroll: true });
  }, []);

  const canvasKbRef = useRef({});
  canvasKbRef.current = {
    copy: copySelection,
    paste: pasteFromClipboard,
    duplicate: duplicateSelection,
    selectAll: selectAllOnCanvas,
    clearSelection: clearCanvasSelection,
    delete: deleteSelection,
    run: runCanvasSelection,
    undo,
    redo,
  };

  useEffect(() => {
    const onKey = (e) => {
      const typing = isTypingTarget(e.target);
      const canvasEl = canvasRootRef.current;
      const inCanvas = !!(canvasEl && (canvasEl === document.activeElement || canvasEl.contains(document.activeElement)));
      const mod = e.ctrlKey || e.metaKey;

      if (e.key === 'Escape') {
        if (typing) return;
        e.preventDefault();
        canvasKbRef.current.clearSelection();
        return;
      }

      if (mod && e.key.toLowerCase() === 'z') {
        if (typing) return;
        e.preventDefault();
        if (e.shiftKey) canvasKbRef.current.redo();
        else canvasKbRef.current.undo();
        return;
      }
      if (!inCanvas || typing) return;
      if (mod && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        canvasKbRef.current.selectAll();
        return;
      }
      if (mod && e.key.toLowerCase() === 'c') {
        e.preventDefault();
        canvasKbRef.current.copy();
        return;
      }
      if (mod && e.key.toLowerCase() === 'v') {
        e.preventDefault();
        canvasKbRef.current.paste();
        return;
      }
      if (mod && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        canvasKbRef.current.duplicate();
        return;
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        canvasKbRef.current.delete();
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        canvasKbRef.current.run();
        return;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // ─── Inspector content ──────────────────────────────────────────────────
  const selNode = selected && nodes.find(n => n.id === selected.id);
  const selKind = selNode?.data?.kind ? NT[selNode.data.kind] : null;
  const selEdge = edgeSel && edges.find(e => e.id === edgeSel);

  return (
    <div
      className={cls('workbench', edgeSel && 'drawer-open')}
      style={{ gridTemplateRows: `48px minmax(0, 1fr) ${bottomHeight}px` }}
    >
      <TopStrip {...{ theme, setTheme, prompt, setPrompt, runAll, pipelineRunning, onOpenReports }}/>
      <div className={cls('workbench-main', edgeSel && 'drawer-open')}>
        <Catalog />
        <div
          ref={canvasRootRef}
          className="canvas workbench-canvas-focus"
          tabIndex={0}
          onMouseDown={(e) => {
            if (!canvasRootRef.current?.contains(e.target)) return;
            if (isTypingTarget(e.target)) return;
            canvasRootRef.current?.focus({ preventScroll: true });
          }}
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}
        >
          <ReactFlow
            nodes={wiredNodes}
            edges={edgesForReactFlow}
            connectionMode={ConnectionMode.Loose}
            nodesConnectable
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onSelectionChange={onSelectionChange}
            onPaneClick={focusCanvas}
            onNodeClick={focusCanvas}
            onEdgeClick={focusCanvas}
            onNodeDragStart={onNodeDragStart}
            nodeTypes={nodeTypes}
            fitView fitViewOptions={{ padding: 0.32, maxZoom: 0.95 }}
            proOptions={{ hideAttribution: true }}
            minZoom={0.4} maxZoom={1.6}
            selectionOnDrag
            panOnDrag={[1, 2]}
            panOnScroll
            defaultEdgeOptions={DEFAULT_FLOW_EDGE_OPTIONS}
            deleteKeyCode={null}
            nodesFocusable={false}
            edgesFocusable={false}
          >
            <Background gap={20} size={1.4} />
            <Controls position="bottom-right" showInteractive={false} />
            {tweaks.showMinimap && (
              <MiniMap
                pannable
                zoomable
                nodeColor={(n) => {
                  if (n.type === 'lane') return 'var(--bg-surface)';
                  if (n.type === 'queryGroup') return 'var(--type-query)';
                  return NT[n.data?.kind]?.color || 'var(--neutral)';
                }}
                maskColor="rgba(0,0,0,.4)"
              />
            )}
          </ReactFlow>
        </div>
        <Inspector selKind={selKind} selNode={selNode} metrics={results.metrics}
                   datasetOptions={datasetOptions} datasetLoadState={datasetLoadState}
                   prompt={prompt} setPrompt={setPrompt}
                   queryContainerMeta={QUERY_CONTAINER}
                   nodes={nodes}
                   edges={edges}
                   patchNodeData={patchNodeData} />
        {selEdge && <Drawer edge={selEdge} nodes={nodes} onClose={() => setEdgeSel(null)} />}
      </div>
      <BottomPanel results={results} prompt={prompt} outputView={outputView} setOutputView={setOutputView}
                   bottomTab={bottomTab} setBottomTab={setBottomTab}
                   pipelineRunning={pipelineRunning} pipelineError={pipelineError}
                   runLog={runLog} runHistory={runHistory}
                   onRestoreRun={restoreHistoryRun} onClearLog={() => setRunLog([])}
                   runSpecs={runSpecs} setRunSpecs={setRunSpecs}
                   runResults={runResults} runsBusy={runsBusy} onRunAll={runAllSpecs}
                   ragasSaveSubdir={ragasSaveSubdir} setRagasSaveSubdir={setRagasSaveSubdir}
                   ragasExportStatus={ragasExportStatus} setRagasExportStatus={setRagasExportStatus}
                   datasetOptions={datasetOptions}
                   queryModules={nodes.filter((n) => n.type === 'queryGroup').map((n) => ({ id: n.id, label: n.data?.label || n.id }))}
                   onStartResize={startBottomResize}/>
      {tweaksOpen && <TweaksPanel tweaks={tweaks} setTweak={setTweak} onClose={() => { setTweaksOpen(false); window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*'); }}/>}
    </div>
  );
}

// ─── useTweaks hook ───────────────────────────────────────────────────────
function useTweaks(defaults) {
  const [t, setT] = useState(defaults);
  const update = useCallback((keyOrObj, val) => {
    const patch = typeof keyOrObj === 'string' ? { [keyOrObj]: val } : keyOrObj;
    setT(prev => ({ ...prev, ...patch }));
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: patch }, '*');
  }, []);
  return [t, update];
}

// ─── Tweaks panel ─────────────────────────────────────────────────────────
function TweaksPanel({ tweaks, setTweak, onClose }) {
  return (
    <div className="tweaks-panel">
      <div className="tweaks-head">
        <span className="tweaks-title">Tweaks</span>
        <button className="btn btn-ghost btn-icon" onClick={onClose}>{I.close}</button>
      </div>
      <div className="tweaks-body">
        <div className="tweaks-section">Canvas</div>
        <TwToggle label="Show minimap"     value={tweaks.showMinimap}    onChange={v => setTweak('showMinimap', v)}/>
        <TwToggle label="Animated edges"   value={tweaks.animatedEdges}  onChange={v => setTweak('animatedEdges', v)}/>
        <div className="tweaks-section">Brand</div>
        <div className="tw-row">
          <span className="tw-label">Accent</span>
          <div className="tw-swatches">
            {['#b189ff','#4088c4','#50b0b5','#d48c46','#ff7fb3','#4be0a8'].map(c => (
              <button key={c} className={cls('tw-swatch', tweaks.accentColor === c && 'active')}
                      style={{ background: c }} onClick={() => setTweak('accentColor', c)}/>
            ))}
          </div>
        </div>
        <div className="tweaks-section">Defaults</div>
        <div className="tw-row">
          <span className="tw-label">Default top-K</span>
          <input className="tw-num" type="number" min="1" max="500"
                 value={tweaks.defaultTopK} onChange={e => setTweak('defaultTopK', +e.target.value)}/>
        </div>
        <div className="tw-row">
          <span className="tw-label">Lane gap (px)</span>
          <input className="tw-num" type="number" min="0" max="200"
                 value={tweaks.laneGap} onChange={e => setTweak('laneGap', +e.target.value)}/>
        </div>
        <div className="tw-hint">Tweaks persist across reloads. Drop new nodes anywhere — they spawn centered on your pointer.</div>
      </div>
    </div>
  );
}
function TwToggle({ label, value, onChange }) {
  return (
    <div className="tw-row" onClick={() => onChange(!value)}>
      <span className="tw-label">{label}</span>
      <div className={cls('node-toggle', value && 'on')}/>
    </div>
  );
}

// ─── Top Strip ──────────────────────────────────────────────────────────────
function TopStrip({ theme, setTheme, prompt, setPrompt, runAll, pipelineRunning, onOpenReports }) {
  const themes = [
    { id: 'dark',      label: 'Dark Synth', bg: '#0e1322',  fg: '#b189ff' },
    { id: 'light',     label: 'Commodore',  bg: '#c8c0b4',  fg: '#4b559f' },
    { id: 'pastel',    label: 'Pastel',     bg: '#fbf4f8',  fg: '#b19cd9' },
    { id: 'neo',       label: 'Neo',        bg: '#04141d',  fg: '#d48c46' },
    { id: 'severance', label: 'Severance',  bg: '#031424',  fg: '#4088c4' },
    { id: 'fallout',   label: 'Fallout',    bg: '#f5ecd8',  fg: '#50b0b5' },
  ];
  return (
    <div className="topstrip">
      <div className="brand">
        <div className="brand-logo">AG</div>
        <span>Antigrav Workbench</span>
        <span className="brand-env">local_dev · graph-rag</span>
      </div>
      <div className="topstrip-prompt">
        {I.prompt}
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Build prompt context…" />
        <span className="kbd">↵</span>
      </div>
      <div className="theme-pick" title="Theme">
        {themes.map(t => (
          <div key={t.id} className={cls('theme-swatch', theme === t.id && 'active')} title={t.label}
               style={{ background: t.bg, color: t.fg }}
               onClick={() => setTheme(t.id)}>
            {theme === t.id ? '●' : ''}
          </div>
        ))}
      </div>
      {onOpenReports && (
        <button className="btn btn-ghost" title="Visualize RAGAS report.json files" onClick={onOpenReports}>
          RAGAS Reports
        </button>
      )}
      <button className="btn btn-ghost btn-icon" title="Reset workspace"
              onClick={() => window.location.reload()}>{I.reset}</button>
      <button className="btn btn-primary" disabled={pipelineRunning} onClick={runAll}>
        {pipelineRunning ? I.zap : I.play} {pipelineRunning ? 'Running…' : 'Execute All'}
      </button>
    </div>
  );
}

// ─── Catalog ────────────────────────────────────────────────────────────────
function Catalog() {
  const [q, setQ] = useState('');
  const match = (n) => !q || n.label.toLowerCase().includes(q.toLowerCase()) || n.id.includes(q.toLowerCase());
  const onDragStart = (e, kind) => {
    e.dataTransfer.setData('application/ag-kind', kind);
    e.dataTransfer.effectAllowed = 'move';
  };
  const renderList = (items) => items.filter(match).map(n => (
    <div key={n.id} className="catalog-item" draggable onDragStart={(e) => onDragStart(e, n.id)}>
      <div className="catalog-item-icon" style={{ background: n.color }}>{n.icon}</div>
      <div>
        <div className="catalog-item-name">{n.label}</div>
        <div className="catalog-item-type">{n.inType || '—'} → {n.outType || '—'}</div>
      </div>
    </div>
  ));
  return (
    <aside className="catalog">
      <div className="catalog-section">
        <h4>Library</h4>
        <div className="catalog-search">
          {I.search}
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search nodes…" />
        </div>
      </div>
      <div className="catalog-section">
        <h4>Pipeline</h4>
        <div className="catalog-hint">Graph construction: dataset → access layer → graph → tags → facets.</div>
        <div className="catalog-list">{renderList(PIPELINE_NODES)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Usage</h4>
        <div className="catalog-hint">The real pipeline. Wire order = run order: prompt → interpret → build input → ground → retrieve A / B → answer → compare.</div>
        <div className="catalog-list">{renderList(USAGE_NODES)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Modules</h4>
        <div className="catalog-hint">Type-safe inserts. A <strong>Probe</strong> is a passthrough — splice it onto any wire whose types match to record what flows through without changing the run.</div>
        <div className="catalog-list">{renderList(MODULE_NODES)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Query module</h4>
        <div className="catalog-hint">Query module: retrieval plan → any <strong>qin</strong> face; <strong>qout</strong> → graph query. Ports appear on each side; extras on the same edge spread out. Arrows always run from source drag to target drop. Invalid pairs stay linked but draw red.</div>
        <div className="catalog-list">
          <div
            className="catalog-item"
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData('application/ag-kind', 'queryContainer');
              e.dataTransfer.effectAllowed = 'move';
            }}
          >
            <div className="catalog-item-icon" style={{ background: QUERY_CONTAINER.color }}>{QUERY_CONTAINER.icon}</div>
            <div>
              <div className="catalog-item-name">{QUERY_CONTAINER.label}</div>
              <div className="catalog-item-type">{QUERY_CONTAINER.inType} → {QUERY_CONTAINER.outType}</div>
            </div>
          </div>
        </div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Query fragments</h4>
        <div className="catalog-hint">Drop <strong>inside</strong> a Query module only. Chain start is seeded automatically.</div>
        <div className="catalog-list">{renderList(QUERY_FRAGMENT_CATALOG)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Lanes</h4>
        <div className="catalog-hint">Drag a Lane to create a runnable A/B branch.</div>
        <div className="catalog-list">
          <div className="catalog-item" draggable onDragStart={(e) => onDragStart(e, 'lane')}>
            <div className="catalog-item-icon" style={{ background: 'var(--accent)' }}>L</div>
            <div>
              <div className="catalog-item-name">New Lane</div>
              <div className="catalog-item-type">runnable group</div>
            </div>
          </div>
        </div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-hint">Tip: connections only join compatible types.</div>
    </aside>
  );
}

// ─── Query module inspector (meaning first; Cypher under Technical) ─────────
function QueryGroupInspector({ selNode, queryContainerMeta, nodes, edges, patchNodeData }) {
  const [tab, setTab] = useState('meaning');
  const composed = useMemo(() => composeModuleCypher(nodes, edges, selNode.id), [nodes, edges, selNode.id]);
  const planRefs = useMemo(() => extractPlanRefs(composed.text), [composed.text]);
  const story = useMemo(
    () => composeHumanStory(nodes, edges, selNode.id, (k) => NT[k]?.label ?? k),
    [nodes, edges, selNode.id],
  );

  return (
    <aside className="inspector">
      <div className="insp-head">
        <div className="insp-title-row">
          <div className="insp-icon" style={{ background: queryContainerMeta.color }}>{queryContainerMeta.icon}</div>
          <div>
            <div className="insp-title">{selNode.data.label || queryContainerMeta.label}</div>
            <div className="insp-meta">{queryContainerMeta.inType} → {queryContainerMeta.outType}</div>
          </div>
        </div>
      </div>
      <div className="insp-tabs">
        {['meaning', 'overview'].map((t) => (
          <button key={t} type="button" className={cls('insp-tab', tab === t && 'active')} onClick={() => setTab(t)}>
            {t === 'meaning' ? 'Meaning' : 'Overview'}
          </button>
        ))}
      </div>
      <div className="insp-body">
        {tab === 'meaning' && (
          <>
            <p className="query-meaning-lead">
              Wire order on the canvas is execution order. This tab is the readable story of what the query does; open <strong>Technical</strong> below when you need generated Cypher or bindings.
            </p>
            <div className="section-head">Intent</div>
            <div className="field">
              <label className="field-label">What this module is for<span className="hint">plain language</span></label>
              <textarea
                className="field-textarea"
                rows={3}
                placeholder="e.g. Pull chunks that match the plan’s topics and entities, within the relevant time window…"
                value={selNode.data.humanSummary ?? ''}
                onChange={(e) => patchNodeData(selNode.id, { humanSummary: e.target.value })}
              />
            </div>
            <div className="section-head">Steps (canvas chain)</div>
            <ol className="query-human-step-list">
              {story.steps.map((s) => (
                <li key={s.id}>
                  <span className="query-human-step-title">{s.title}</span>
                  <div className="query-human-step-body">{s.body}</div>
                </li>
              ))}
            </ol>
            {story.warnings.map((w) => (
              <div key={w} className="query-human-warn">{w}</div>
            ))}
            <details className="query-tech-block">
              <summary className="query-tech-summary">Technical · generated Cypher & bindings</summary>
              <div className="query-tech-inner">
                <div className="section-head query-tech-section-head">Header & footer</div>
                <div className="field">
                  <label className="field-label">MATCH / preamble</label>
                  <textarea
                    className="field-textarea query-syntax-input"
                    rows={5}
                    value={selNode.data.headerCypher ?? DEFAULT_MODULE_HEADER}
                    onChange={(e) => patchNodeData(selNode.id, { headerCypher: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label className="field-label">RETURN / tail</label>
                  <textarea
                    className="field-textarea query-syntax-input"
                    rows={4}
                    value={selNode.data.footerCypher ?? DEFAULT_MODULE_FOOTER}
                    onChange={(e) => patchNodeData(selNode.id, { footerCypher: e.target.value })}
                  />
                </div>
                <div className="field">
                  <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }}
                          onClick={() => patchNodeData(selNode.id, { headerCypher: DEFAULT_MODULE_HEADER, footerCypher: DEFAULT_MODULE_FOOTER })}>
                    Reset header/footer to defaults
                  </button>
                </div>
                <div className="section-head query-tech-section-head">Node order → clause order</div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 8 }}>
                  {composed.chain.length ? composed.chain.map((c) => NT[c.kind]?.label ?? c.kind).join(' → ') : '—'}
                </div>
                {composed.warnings.map((w) => (
                  <div key={w} style={{ fontSize: 11, color: 'var(--warn)', marginBottom: 8 }}>{w}</div>
                ))}
                <div className="section-head query-tech-section-head">Plan fields referenced</div>
                <div className="query-syntax-chip-row">
                  {planRefs.length ? planRefs.map((r) => (
                    <span key={r} className="query-syntax-chip">{r}</span>
                  )) : <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>None detected</span>}
                </div>
                <div className="section-head query-tech-section-head">Assembled Cypher</div>
                <pre className="query-syntax-preview">{composed.text || '—'}</pre>
                <div className="section-head query-tech-section-head">Demo binding (preview only)</div>
                <pre className="query-syntax-preview query-syntax-preview-sub">{JSON.stringify(DEMO_PLAN_PREVIEW, null, 2)}</pre>
              </div>
            </details>
          </>
        )}
        {tab === 'overview' && (
          <>
            <div className="section-head">How it connects</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>
              Left handle brings in the retrieval <strong>plan</strong>. Inner nodes are steps—left-to-right chain is the order those steps apply. Right handle sends the query plan to Graph Query. The GUI shows what each step <em>means</em>; Cypher is optional detail under Technical.
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

function QueryFragmentSyntaxSection({ kind, selNode, nodes, edges, patchNodeData }) {
  const taRef = useRef(null);
  const parentId = selNode.parentId;
  const composed = useMemo(
    () => (parentId ? composeModuleCypher(nodes, edges, parentId) : null),
    [nodes, edges, parentId],
  );
  const val = getFragmentTemplate(selNode, kind);
  const defaultWording = FRAGMENT_HUMAN_DEFAULTS[kind] ?? '';

  const insertSnippet = useCallback((text) => {
    const el = taRef.current;
    if (!el) return;
    const a = el.selectionStart ?? el.value.length;
    const b = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, a);
    const after = el.value.slice(b);
    const next = before + text + after;
    patchNodeData(selNode.id, { cypherTemplate: next });
    requestAnimationFrame(() => {
      el.focus();
      const p = a + text.length;
      el.setSelectionRange(p, p);
    });
  }, [patchNodeData, selNode.id]);

  return (
    <>
      <p className="query-meaning-lead">
        The graph shows <strong>intent</strong> first—this text is what the step does for readers. Expand <strong>Technical</strong> to view or edit the Cypher that implements it (e.g. after you click in or focus the editor).
      </p>
      <div className="section-head">Meaning</div>
      <div className="field">
        <label className="field-label">What this step does</label>
        <textarea
          className="field-textarea"
          rows={4}
          placeholder={defaultWording}
          value={selNode.data.humanNote ?? ''}
          onChange={(e) => patchNodeData(selNode.id, { humanNote: e.target.value })}
        />
      </div>
      <div className="field">
        <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }}
                onClick={() => patchNodeData(selNode.id, { humanNote: '' })}>
          Restore default wording
        </button>
      </div>
      <details className="query-tech-block">
        <summary className="query-tech-summary">Technical · Cypher fragment</summary>
        <div className="query-tech-inner">
          <div className="field">
            <label className="field-label">Fragment<span className="hint">after previous step; <code className="query-syntax-code">plan</code> after WITH</span></label>
            <div className="query-syntax-toolbar">
              {PLAN_INSERTS.map((p) => (
                <button key={p.label} type="button" className="query-syntax-pill" onClick={() => insertSnippet(p.text)}>
                  + {p.label}
                </button>
              ))}
            </div>
            <textarea
              ref={taRef}
              className="field-textarea query-syntax-input"
              rows={8}
              value={val}
              onChange={(e) => patchNodeData(selNode.id, { cypherTemplate: e.target.value })}
              spellCheck={false}
            />
          </div>
          <div className="field">
            <button type="button" className="btn btn-ghost" style={{ fontSize: 11 }}
                    onClick={() => patchNodeData(selNode.id, { cypherTemplate: FRAGMENT_TEMPLATE_DEFAULTS[kind] ?? '' })}>
              Reset Cypher to default
            </button>
          </div>
        </div>
      </details>
      {composed && (
        <details className="query-tech-block">
          <summary className="query-tech-summary">Technical · full module Cypher</summary>
          <pre className="query-syntax-preview">{composed.text}</pre>
        </details>
      )}
    </>
  );
}

// ─── Inspector ──────────────────────────────────────────────────────────────
function Inspector({ selKind, selNode, metrics, datasetOptions, datasetLoadState, prompt, setPrompt, queryContainerMeta, nodes, edges, patchNodeData }) {
  const [tab, setTab] = useState('config');
  if (!selNode) {
    return (
      <aside className="inspector">
        <div className="insp-empty">
          <div>
            <div className="insp-empty-glyph">{I.inspect}</div>
            <div className="insp-empty-title">Nothing selected</div>
            <div className="insp-empty-sub">Click a node to inspect its config and the real metrics from the last run. Click an edge to see the data contract on the wire.</div>
          </div>
        </div>
      </aside>
    );
  }
  if (selNode.type === 'lane') {
    return (
      <aside className="inspector">
        <div className="insp-head">
          <div className="insp-title-row">
            <div className="insp-icon" style={{ background: 'var(--accent)' }}>L</div>
            <div>
              <div className="insp-title">{selNode.data.label}</div>
              <div className="insp-meta">{selNode.id}</div>
            </div>
          </div>
        </div>
        <div className="insp-body">
          <div className="section-head">Lane Status</div>
          <div className="stat-grid">
            <div className="stat-card"><div className="stat-card-label">Last run</div><div className="stat-card-val">{selNode.data.lastRun ? `${selNode.data.lastRun}ms` : '—'}</div></div>
            <div className="stat-card"><div className="stat-card-label">State</div><div className="stat-card-val" style={{fontSize:13}}>{selNode.data.running ? 'running' : 'ready'}</div></div>
          </div>
          <div className="section-head">About lanes</div>
          <div style={{fontSize:11.5,color:'var(--text-muted)',lineHeight:1.55}}>
            A lane is a runnable group. The Execute button runs every connected node inside the lane in topological order, then publishes the result to the bottom comparison panel. Drop a lane inside another lane to nest pipelines.
          </div>
        </div>
      </aside>
    );
  }

  if (selNode.type === 'queryGroup') {
    return (
      <QueryGroupInspector
        selNode={selNode}
        queryContainerMeta={queryContainerMeta}
        nodes={nodes}
        edges={edges}
        patchNodeData={patchNodeData}
      />
    );
  }

  return (
    <aside className="inspector">
      <div className="insp-head">
        <div className="insp-title-row">
          <div className="insp-icon" style={{ background: selKind.color }}>{selKind.icon}</div>
          <div>
            <div className="insp-title">{selKind.label}</div>
            <div className="insp-meta">{selKind.inType || '—'} → {selKind.outType || '—'}</div>
          </div>
        </div>
      </div>
      <div className="insp-tabs">
        {['config','metrics'].map(t => (
          <button key={t} className={cls('insp-tab', tab === t && 'active')} onClick={() => setTab(t)}>
            {t === 'config' ? 'Config' : 'Metrics'}
          </button>
        ))}
      </div>
      <div className="insp-body">
        {tab === 'config' && (
          <ConfigForm
            kind={selKind.id}
            selNode={selNode}
            datasetOptions={datasetOptions}
            datasetLoadState={datasetLoadState}
            prompt={prompt}
            setPrompt={setPrompt}
            syntaxCtx={{ selNode, nodes, edges, patchNodeData }}
          />
        )}
        {tab === 'metrics' && (
          <NodeMetricsPanel kind={selKind.id} metrics={metrics} selNode={selNode} prompt={prompt}/>
        )}
      </div>
    </aside>
  );
}

const MODEL_OPTIONS = ['claude-haiku-4-5', 'claude-sonnet-4-5', 'claude-opus-4-6', 'gpt-4o-mini', 'gpt-4o'];

function ModelField({ label, hint, value, onChange }) {
  return (
    <div className="field">
      <label className="field-label">{label}<span className="hint">{hint}</span></label>
      <select className="field-select" value={value || '__default'}
              onChange={(e) => onChange(e.target.value === '__default' ? '' : e.target.value)}>
        <option value="__default">Default (connection model)</option>
        {MODEL_OPTIONS.map((m) => <option key={m}>{m}</option>)}
      </select>
    </div>
  );
}

const OfflineNote = ({ children }) => (
  <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>{children}</div>
);

/**
 * Per-node configuration. For the executable Usage nodes this edits the
 * selected node's own `data` (params live on the node, per the engine) so the
 * wired graph runs exactly as configured. Pipeline-lane nodes are the offline
 * Python build and carry no live tunable.
 */
function ConfigForm({ kind, selNode, datasetOptions, datasetLoadState, prompt, setPrompt, syntaxCtx }) {
  const d = selNode?.data || {};
  const setData = (patch) => syntaxCtx.patchNodeData(selNode.id, patch);

  if (kind === 'prompt') {
    return (
      <>
        <div className="field">
          <label className="field-label">Prompt<span className="hint">the user query (shared)</span></label>
          <textarea className="field-textarea" value={prompt} onChange={(e) => setPrompt(e.target.value)}/>
        </div>
        <div className="field">
          <label className="field-label">Mode<span className="hint">how the prompt reaches the LLM</span></label>
          <select className="field-select" value={d.mode || 'context'}
                  onChange={(e) => setData({ mode: e.target.value })}>
            <option value="context">Build prompt context (api-mode)</option>
            <option value="raw">Raw prompt only</option>
            <option value="hybrid">Hybrid: context + system</option>
          </select>
        </div>
      </>
    );
  }

  if (kind === 'interpret') {
    return <ModelField label="Interpreter model" hint="2-pass plan + gate"
                       value={d.model} onChange={(v) => setData({ model: v })}/>;
  }

  if (kind === 'build_input') {
    const options = datasetOptions?.length ? datasetOptions : DATASETS;
    const facets = Array.isArray(d.activeFacets) ? d.activeFacets : [];
    const toggleFacet = (id) =>
      setData({ activeFacets: facets.includes(id) ? facets.filter((f) => f !== id) : [...facets, id] });
    return (
      <>
        <div className="field">
          <label className="field-label">Dataset<span className="hint">:File.dataset_id filter</span></label>
          <select className="field-select" value={d.datasetId || ''} onChange={(e) => setData({ datasetId: e.target.value })}>
            {options.map((o) => <option key={o.id} value={o.id}>{o.id}</option>)}
          </select>
          {datasetLoadState?.error && (
            <div className="tweaks-hint" style={{ marginTop: 6 }}>Live source list unavailable; showing static datasets.</div>
          )}
          {datasetLoadState?.loading && (
            <div className="tweaks-hint" style={{ marginTop: 6 }}>Loading graph sources…</div>
          )}
        </div>
        <div className="field">
          <label className="field-label">Active facets<span className="hint">HAS_TAG dimensions scored</span></label>
          <div className="facet-grid">
            {FACETS.map((c) => (
              <div key={c.id} className={cls('facet-chip', facets.includes(c.id) && 'on')}
                   title={c.hint} onClick={() => toggleFacet(c.id)}>
                <span className="facet-chip-dot"/>{c.label}
              </div>
            ))}
          </div>
        </div>
        <div className="field">
          <label className="field-label">Max chunks<span className="hint">limit per lane</span></label>
          <input className="field-input" type="number" min="1" max="500" value={d.maxChunks ?? 50}
                 onChange={(e) => setData({ maxChunks: Math.max(1, +e.target.value || 1) })}/>
        </div>
        <div className="field">
          <label className="field-label">Grounding depth (k)<span className="hint">corpus tags / prompt tag</span></label>
          <input className="field-input" type="number" min="1" max="50" value={d.groundingK ?? 10}
                 onChange={(e) => setData({ groundingK: Math.max(1, +e.target.value || 1) })}/>
        </div>
        <div className="field">
          <label className="field-label">Min similarity<span className="hint">{Number(d.minSim ?? 0.78).toFixed(2)}</span></label>
          <input className="field-input" type="range" min="0" max="1" step="0.01" value={d.minSim ?? 0.78}
                 onChange={(e) => setData({ minSim: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Min tag weight<span className="hint">{Number(d.weightThreshold ?? 0).toFixed(2)}</span></label>
          <input className="field-input" type="range" min="0" max="1" step="0.05" value={d.weightThreshold ?? 0}
                 onChange={(e) => setData({ weightThreshold: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Min file relevance<span className="hint">{Number(d.minRelevanceToFile ?? 0).toFixed(2)}</span></label>
          <input className="field-input" type="range" min="0" max="1" step="0.05" value={d.minRelevanceToFile ?? 0}
                 onChange={(e) => setData({ minRelevanceToFile: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Run id<span className="hint">HAS_TAG edge filter</span></label>
          <input className="field-input" value={d.runId || DONE_GRAPH_RUN_ID} readOnly/>
        </div>
      </>
    );
  }

  if (kind === 'ground') {
    return <OfflineNote>Embeds the plan tags with the bundled e5 model and kNN-grounds
      them onto corpus <code>:Tag</code>s (validating dataset + hard gate first).
      Knobs (k, min&nbsp;similarity) live on <strong>Build input</strong> since they
      shape the <code>RetrievalInput</code> this consumes.</OfflineNote>;
  }
  if (kind === 'retrieve_tags') {
    return <OfflineNote>Lane A: scores chunks with the weighted-overlap Cypher over
      the grounded corpus tags. No own knobs — thresholds/limit come from the
      <code> RetrievalInput</code> built upstream.</OfflineNote>;
  }
  if (kind === 'retrieve_baseline') {
    return <OfflineNote>Lane B: relevance-to-file ordering only (no tags), same hard
      gate and dataset scope. The control comparison for the thesis.</OfflineNote>;
  }
  if (kind === 'answer') {
    return (
      <>
        <ModelField label="Answer model" hint="LLM over retrieved chunks"
                    value={d.model} onChange={(v) => setData({ model: v })}/>
        <OfflineNote>Prompt mode comes from the <strong>Prompt</strong> node;
          this node answers over whatever chunks are wired into it.</OfflineNote>
      </>
    );
  }
  if (kind === 'compare') {
    return <OfflineNote>Joins the A and B answers, computes the real metrics
      (grounding, A/B overlap, citations, per-stage latency) and publishes the
      result to the console. Must be the terminal node — it produces the run
      output.</OfflineNote>;
  }
  if (kind === 'probe') {
    return (
      <div className="field">
        <label className="field-label">Label<span className="hint">shown in the run log</span></label>
        <input className="field-input" value={d.label || ''} placeholder="probe"
               onChange={(e) => setData({ label: e.target.value })}/>
        <div className="tweaks-hint" style={{ marginTop: 6 }}>
          Typed passthrough: records what flows through and changes nothing.
          Splice it onto any wire whose types match.
        </div>
      </div>
    );
  }

  if (kind.startsWith('qf_') && syntaxCtx?.selNode && syntaxCtx?.patchNodeData) {
    return (
      <QueryFragmentSyntaxSection
        kind={kind}
        selNode={syntaxCtx.selNode}
        nodes={syntaxCtx.nodes}
        edges={syntaxCtx.edges}
        patchNodeData={syntaxCtx.patchNodeData}
      />
    );
  }

  if (kind === 'dataset' || kind === 'access' || kind === 'index' || kind === 'tags' || kind === 'facets') {
    return (
      <OfflineNote>
        <strong>Pipeline lane — offline.</strong> The dataset → access → index →
        tags → facets graph is built by the Python pipeline (<code>python -m
        tagging</code>) and read here as-is. It is an illustration of how the
        graph was constructed; nothing here is executed in the browser. The live
        retrieval scope (dataset, facets, run id) is set on the Usage lane’s
        <strong> Build input</strong> node.
      </OfflineNote>
    );
  }

  return <OfflineNote>No configuration for this node.</OfflineNote>;
}

function fmtMs(v) { return v == null ? '—' : `${v}ms`; }
function fmtStat(s, d = 2) {
  if (!s) return '—';
  return `${s.min.toFixed(d)}–${s.max.toFixed(d)} · μ ${s.mean.toFixed(d)}`;
}
function pctText(x) { return Number.isFinite(x) ? `${(x * 100).toFixed(0)}%` : '—'; }

function MetricCards({ items }) {
  return (
    <div className="stat-grid">
      {items.map(([label, val, sub]) => (
        <div key={label} className="stat-card">
          <div className="stat-card-label">{label}</div>
          <div className="stat-card-val" style={{ fontSize: 13 }}>{val}</div>
          {sub != null && <div className="stat-card-sub">{sub}</div>}
        </div>
      ))}
    </div>
  );
}

/**
 * Per-node metrics from the last *real* run only. Every number here is
 * computed in runPipeline from the actual interpret/ground/retrieve/answer
 * results — there is no sample/placeholder path. Nodes with no in-browser
 * instrumentation say so plainly.
 */
function NodeMetricsPanel({ kind, metrics, selNode, prompt }) {
  const d = selNode?.data || {};
  const NotRun = (
    <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>
      No run yet. Execute the Usage lane — these are populated only from a real
      prompt → interpret → retrieve → answer run, never sample data.
    </div>
  );

  if (kind === 'prompt') {
    return (
      <>
        <div className="section-head">Prompt</div>
        <MetricCards items={[
          ['Length', `${prompt.length} chars`],
          ['Mode', d.mode || 'context'],
        ]}/>
      </>
    );
  }

  if (kind === 'dataset' || kind === 'access' || kind === 'index' || kind === 'tags' || kind === 'facets') {
    return (
      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>
        Pipeline lane — built offline by the Python pipeline. No per-run metric
        in the browser. Live run metrics are on the Usage lane (Ground,
        Retrieve&nbsp;A/B, Answer, Compare) and in the result console.
      </div>
    );
  }

  if (kind === 'interpret') {
    if (!metrics) return NotRun;
    const g = metrics.grounding;
    return (
      <>
        <div className="section-head">Stage latency (last run)</div>
        <MetricCards items={[['Interpret', fmtMs(metrics.latency.interpret)]]}/>
        <div className="section-head">Plan</div>
        <MetricCards items={[
          ['Prompt tags', g ? g.promptTags : '—'],
        ]}/>
      </>
    );
  }

  if (kind === 'build_input') {
    return (
      <>
        <div className="section-head">Configured scope</div>
        <MetricCards items={[
          ['Dataset', d.datasetId || 'all'],
          ['Max chunks', d.maxChunks ?? 50],
          ['Grounding k', d.groundingK ?? 10],
          ['Min sim', Number(d.minSim ?? 0.78).toFixed(2)],
        ]}/>
        <div className="section-head">Active facets</div>
        <div className="tag-row">
          {(Array.isArray(d.activeFacets) ? d.activeFacets : []).length
            ? d.activeFacets.map((f) => <span key={f} className="tag-pill">{f}</span>)
            : <span style={{ fontSize: 11, color: 'var(--err)' }}>none — Retrieve A returns nothing</span>}
        </div>
      </>
    );
  }

  if (kind === 'ground') {
    if (!metrics) return NotRun;
    const g = metrics.grounding;
    return (
      <>
        <div className="section-head">Grounding quality (last run)</div>
        {g ? (
          <>
            <MetricCards items={[
              ['Prompt tags', g.promptTags],
              ['Grounded corpus tags', g.groundedTags],
              ['Cosine min/μ/max', fmtStat(g.sim, 3)],
              ['Zero-grounded', g.zeroGrounded.length],
              ['Latency', fmtMs(metrics.latency.ground)],
            ]}/>
            {g.zeroGrounded.length > 0 && (
              <div style={{ fontSize: 10.5, color: 'var(--warn)', marginTop: 6 }}>
                off-corpus prompt tags: {g.zeroGrounded.join(', ')}
              </div>
            )}
          </>
        ) : (
          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
            No grounding ran (no prompt tags, or the hard-gate / lexical path was used).
          </div>
        )}
      </>
    );
  }

  if (kind === 'retrieve_tags' || kind === 'retrieve_baseline') {
    if (!metrics) return NotRun;
    const isA = kind === 'retrieve_tags';
    const s = isA ? metrics.retrieval.A : metrics.retrieval.B;
    const { overlap } = metrics.retrieval;
    return (
      <>
        <div className="section-head">{isA ? 'Lane A — HERB tags' : 'Lane B — baseline'}</div>
        <MetricCards items={[
          ['Chunks', s.count],
          ['Distinct files', s.files],
          ['Score min/μ/max', fmtStat(s.score)],
          ['Rel min/μ/max', fmtStat(s.rel)],
          ['Latency', fmtMs(isA ? metrics.latency.retrieveA : metrics.latency.retrieveB)],
        ]}/>
        <div className="section-head">A vs B overlap</div>
        <MetricCards items={[
          ['Shared chunks', overlap.count],
          ['Jaccard', overlap.jaccard.toFixed(3)],
        ]}/>
      </>
    );
  }

  if (kind === 'answer') {
    if (!metrics) return NotRun;
    const { A, B } = metrics.citations;
    return (
      <>
        <div className="section-head">Lane A — answer grounding</div>
        <MetricCards items={[
          ['Citations', A.total],
          ['Distinct chunks', A.distinct],
          ['Retrieved used', pctText(A.pctUsed)],
          ['Answer latency', fmtMs(metrics.latency.answerA)],
        ]}/>
        <div className="section-head">Lane B — answer grounding</div>
        <MetricCards items={[
          ['Citations', B.total],
          ['Distinct chunks', B.distinct],
          ['Retrieved used', pctText(B.pctUsed)],
          ['Answer latency', fmtMs(metrics.latency.answerB)],
        ]}/>
      </>
    );
  }

  if (kind === 'compare') {
    if (!metrics) return NotRun;
    const { overlap } = metrics.retrieval;
    const L = metrics.latency;
    return (
      <>
        <div className="section-head">A vs B</div>
        <MetricCards items={[
          ['Shared chunks', overlap.count],
          ['Jaccard', overlap.jaccard.toFixed(3)],
          ['A cites', metrics.citations.A.distinct],
          ['B cites', metrics.citations.B.distinct],
        ]}/>
        <div className="section-head">Per-stage latency</div>
        <MetricCards items={[
          ['Interpret', fmtMs(L.interpret)],
          ['Ground', fmtMs(L.ground)],
          ['Retrieve A', fmtMs(L.retrieveA)],
          ['Retrieve B', fmtMs(L.retrieveB)],
          ['Answer A', fmtMs(L.answerA)],
          ['Answer B', fmtMs(L.answerB)],
          ['Total', fmtMs(L.total)],
        ]}/>
      </>
    );
  }

  if (kind === 'probe') {
    return (
      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>
        Passthrough — records the value flowing through to the run log
        (Logs tab), changes nothing. No metric of its own.
      </div>
    );
  }

  return (
    <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.55 }}>
      No standalone metric for this node — see Ground, Retrieve A/B, Answer and
      Compare for the live run breakdown.
    </div>
  );
}

// ─── Edge Drawer ────────────────────────────────────────────────────────────
function Drawer({ edge, nodes, onClose }) {
  const sNode = nodes.find(n => n.id === edge.source);
  const tNode = nodes.find(n => n.id === edge.target);
  const sKind = sNode?.type === 'queryGroup'
    ? { label: 'Query module', outType: QUERY_CONTAINER.outType, inType: null, id: 'queryGroup' }
    : (sNode?.data?.kind ? NT[sNode.data.kind] : null);
  const tKind = tNode?.type === 'queryGroup'
    ? { label: 'Query module', outType: null, inType: QUERY_CONTAINER.inType, id: 'queryGroup' }
    : (tNode?.data?.kind ? NT[tNode.data.kind] : null);
  return (
    <aside className="drawer">
      <div className="drawer-head">
        <span className="drawer-head-pill">{I.link} edge</span>
        <div className="drawer-title">Data contract on the wire</div>
        <button className="btn btn-ghost btn-icon" onClick={onClose}>{I.close}</button>
      </div>
      <div className="drawer-body">
        {edge.data?.contractOk === false && (
          <div className="drawer-warn">
            This connection does not match the pipeline type rules (shown in red on the canvas).
          </div>
        )}
        <div className="drawer-flow">
          <div className="drawer-flow-cell">
            <div className="drawer-flow-name">{sKind?.label || '—'}</div>
            <div className="drawer-flow-type">{sKind?.outType || ''}</div>
          </div>
          <div className="drawer-flow-arrow">→</div>
          <div className="drawer-flow-cell">
            <div className="drawer-flow-name">{tKind?.label || '—'}</div>
            <div className="drawer-flow-type">{tKind?.inType || ''}</div>
          </div>
        </div>
        <div className="section-head">Payload type</div>
        <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginBottom: 4 }}>
          <code className="query-syntax-code">{edge.data?.type || 'untyped'}</code> — the
          declared contract carried by this connection. Live counts and timings
          are per run in the Inspector <strong>Metrics</strong> tab and the result console.
        </div>
        <div className="section-head">Schema</div>
        <div className="sample-table">
          <div className="sample-row head"><span className="col col-id">field</span><span className="col">type</span><span className="col col-w"></span></div>
          {schemaFor(edge.data?.type).map((f,i) => (
            <div key={i} className="sample-row">
              <span className="col col-id">{f.name}</span>
              <span className="col" style={{color:'var(--text-muted)'}}>{f.type}</span>
              <span className="col col-w"></span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
function schemaFor(t) {
  switch (t) {
    case 'prompt':     return [{name:'context',type:'string'},{name:'mode',type:'enum'}];
    case 'source':     return [{name:'datasetId',type:'string'},{name:'fileCount',type:'int'},{name:'chunkCount',type:'int'}];
    case 'files':      return [{name:'fileId',type:'string'},{name:'relPath',type:'string'},{name:'formatFamily',type:'string'}];
    case 'graph':      return [{name:'source',type:'Source'},{name:'files[]',type:'File[]'},{name:'chunks[]',type:'Chunk[]'}];
    case 'graph_scope':return [{name:'tagsEnabled',type:'boolean'},{name:'facets',type:'FacetDimension[]'}];
    case 'retrieval_plan': return [{name:'plan',type:'QueryPlan'},{name:'scope',type:'{datasetId,runId}'},{name:'controls',type:'RetrievalControls + excludedSections'},{name:'gate',type:'HardGate'}];
    case 'context':    return [{name:'chunkId',type:'string'},{name:'fileId',type:'string'},{name:'content',type:'text'},{name:'tags[]',type:'ChunkTag'},{name:'score',type:'float'}];
    case 'query_plan': return [{name:'extractedTags',type:'string[]'},{name:'facets',type:'FacetDimension[]'},{name:'strategy',type:'enum'}];
    case 'frag':       return [{name:'slotId',type:'string'},{name:'boundParams',type:'Record<string, unknown>'}];
    case 'result':     return [{name:'llmResponse',type:'string'},{name:'tokensIn',type:'int'},{name:'tokensOut',type:'int'},{name:'durationMs',type:'int'}];
    default: return [];
  }
}

// ─── Bottom Panel (lane comparison) ─────────────────────────────────────────
function copyText(text) {
  if (!text) return;
  navigator.clipboard?.writeText(text).catch(() => {});
}

/**
 * Offline RAGAS input. Real run data only; failed/empty runs are skipped, not
 * faked. Two entry shapes are emitted into one superset row so both the in-app
 * scorer and the headless `frontend/scripts/ragas-export.ts` Python consumer
 * read it:
 *  - Run Builder runs → one row per Run (its config in `meta`).
 *  - legacy canvas A/B runs → one row per lane.
 */
async function exportRagasJsonl(runs, saveSubdir, onStatus) {
  const rows = [];
  const push = (o) => rows.push(JSON.stringify(o));
  for (const run of runs) {
    if (run.kind === 'run') {
      const r = run.runResult;
      if (!r) continue;
      const ctx = (r.retrievedChunks || []).map((c) => c.content).filter(Boolean);
      push({
        id: run.id, run_id: run.id, at: run.at,
        question: run.prompt, user_input: run.prompt,
        answer: r.response || '', response: r.response || '',
        contexts: ctx, retrieved_contexts: ctx,
        reference: null,
        meta: {
          label: r.label, route: r.route, database: r.database,
          dataset_id: run.datasetId || null, spec: run.spec,
          n_chunks: r.chunks, tokens: { in: r.tokensIn, out: r.tokensOut },
          elapsed_ms: r.durationMs,
        },
      });
      continue;
    }
    if (!run.results) continue;
    for (const lane of ['A', 'B']) {
      const r = run.results[`lane_${lane}`];
      if (!r) continue;
      const ctx = (r.retrievedChunks || []).map((c) => c.content).filter(Boolean);
      push({
        id: `${run.id}#${lane}`, run_id: run.id, at: run.at, lane,
        dataset: run.datasetId || null,
        question: run.prompt, user_input: run.prompt,
        answer: r.response || '', response: r.response || '',
        contexts: ctx, retrieved_contexts: ctx, reference: null,
      });
    }
  }
  if (!rows.length) return;
  const filename = `ragas_runs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.jsonl`;
  const text = rows.join('\n') + '\n';
  try {
    onStatus?.('Saving…');
    const path = await saveRagasArtifact(filename, text, saveSubdir);
    onStatus?.(path ? `Saved ${path}` : `Downloaded ${filename}`);
  } catch (e) {
    onStatus?.(`Export failed: ${e?.message || e}`);
  }
}

function BottomPanel({
  results, prompt, outputView, setOutputView, bottomTab, setBottomTab,
  pipelineRunning, pipelineError, runLog, runHistory, onRestoreRun, onClearLog, onStartResize,
  runSpecs, setRunSpecs, runResults, runsBusy, onRunAll, datasetOptions, queryModules,
  ragasSaveSubdir, setRagasSaveSubdir, ragasExportStatus, setRagasExportStatus,
}) {
  const [errorsOpen, setErrorsOpen] = useState(false);
  const [copiedErrorId, setCopiedErrorId] = useState(null);
  const a = results.lane_A, b = results.lane_B;
  const tabs = [
    ['comparison', 'Comparison'],
    ['runs', `Run Builder ${runSpecs?.length ? `· ${runSpecs.length}` : ''}`],
    ['logs', `Logs ${runLog.length}`],
    ['history', `History ${runHistory.length}`],
  ];
  const errorItems = useMemo(() => {
    const items = [];
    if (pipelineError) {
      items.push({
        id: 'current',
        at: 'current',
        stage: 'pipeline',
        message: pipelineError,
      });
    }
    for (const ev of runLog.filter((x) => x.status === 'failed').slice().reverse()) {
      items.push({
        id: ev.id,
        at: ev.at,
        stage: ev.stage,
        message: ev.message,
      });
    }
    const seen = new Set();
    return items.filter((item) => {
      const key = `${item.stage}:${item.message}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [pipelineError, runLog]);
  const copyError = (item) => {
    copyText(item.message);
    setCopiedErrorId(item.id);
    window.setTimeout(() => setCopiedErrorId(null), 900);
  };
  return (
    <section className="bottom">
      <div className="bottom-resizer" onPointerDown={onStartResize} title="Resize results panel" />
      <div className="bottom-head">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={cls('bottom-tab', bottomTab === key && 'active')}
            onClick={() => setBottomTab(key)}
          >
            {key === 'comparison' && I.layers}{label}
          </button>
        ))}
        <div style={{flex:1}}/>
        {pipelineRunning && (
          <span style={{fontSize:11,color:'var(--accent)',marginRight:12,animation:'pulse 1.2s infinite'}}>
            {I.zap} Running pipeline…
          </span>
        )}
        {pipelineError && !pipelineRunning && (
          <div className="error-summary">
            <span className="error-summary-text" title={pipelineError}>⚠ {pipelineError}</span>
            <button
              type="button"
              className={cls('error-list-button', errorsOpen && 'active')}
              onClick={() => setErrorsOpen((v) => !v)}
              title="Show error list"
            >
              {I.list}
              <span>{errorItems.length}</span>
            </button>
            {errorsOpen && (
              <div className="error-popover">
                <div className="error-popover-head">
                  <span>Error list</span>
                  <button type="button" onClick={() => setErrorsOpen(false)}>Close</button>
                </div>
                <div className="error-popover-list">
                  {errorItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="error-popover-row"
                      onClick={() => copyError(item)}
                    >
                      <span className="error-popover-meta">{item.at} · {item.stage}</span>
                      <span className="error-popover-message">{item.message}</span>
                      <span className="error-popover-copy">{copiedErrorId === item.id ? 'copied' : 'copy'}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {(bottomTab === 'comparison' || bottomTab === 'runs') && (
          <div className="bottom-pane-mode">
            {[['llm','Answer'],['chunks','Chunks'],['table','Run data']].map(([k,l]) =>
              <button key={k} className={cls(outputView === k && 'active')} onClick={() => setOutputView(k)}>{l}</button>)}
          </div>
        )}
      </div>
      {bottomTab === 'comparison' && (
        <div className="bottom-body">
          <ResultPane label="Lane A — HERB tags" tone="full" data={a} view={outputView}/>
          <ResultPane label="Lane B — baseline (no tags)" tone="baseline" data={b} view={outputView}/>
        </div>
      )}
      {bottomTab === 'runs' && (
        <RunBuilderPanel
          prompt={prompt}
          runSpecs={runSpecs} setRunSpecs={setRunSpecs}
          runResults={runResults} runsBusy={runsBusy} onRunAll={onRunAll}
          datasetOptions={datasetOptions} queryModules={queryModules}
          outputView={outputView}
          ragasSaveSubdir={ragasSaveSubdir} setRagasSaveSubdir={setRagasSaveSubdir}
          ragasExportStatus={ragasExportStatus} setRagasExportStatus={setRagasExportStatus}
        />
      )}
      {bottomTab === 'logs' && <LogPanel events={runLog} pipelineError={pipelineError} onClearLog={onClearLog}/>}
      {bottomTab === 'history' && (
        <HistoryPanel
          runs={runHistory} prompt={prompt} onRestoreRun={onRestoreRun}
          ragasSaveSubdir={ragasSaveSubdir} setRagasExportStatus={setRagasExportStatus}
        />
      )}
    </section>
  );
}

function formatRetrievalGate(gate) {
  if (!gate) return 'none';
  const parts = [];
  for (const key of ['product', 'section', 'channel', 'employee_id']) {
    if (gate[key]) parts.push(`${key}=${gate[key]}`);
  }
  if (gate.years?.length) parts.push(`years=${gate.years.join(',')}`);
  return parts.length ? parts.join(' · ') : 'none';
}

function ResultPane({ label, tone, data, view }) {
  const [chunkFilter, setChunkFilter] = useState('');
  const [selectedChunkKey, setSelectedChunkKey] = useState(null);
  if (!data) return <div className="bottom-pane"><div className="bottom-pane-empty">Run the lane to see results.</div></div>;
  const liveChunks = data.retrievedChunks;
  const isDemo = !liveChunks;
  const rInput = data.retrievalInput;
  const sourceChunks = liveChunks ?? SAMPLE_CHUNKS.slice(0, tone === 'full' ? 4 : 5);
  const normalizedChunks = sourceChunks.map((c, i) => ({
    key: c.chunkId || c.id || `chunk_${i}`,
    score: c.score ?? c.rel ?? 0,
    relevanceToFile: c.relevanceToFile ?? c.rel ?? null,
    description: c.description || c.preview || '',
    content: c.content || c.preview || '',
    fileId: c.fileId || c.file || 'sample',
  }));
  const q = chunkFilter.trim().toLowerCase();
  const filteredChunks = q
    ? normalizedChunks.filter((c) => `${c.description} ${c.content} ${c.fileId}`.toLowerCase().includes(q))
    : normalizedChunks;
  const selectedChunk = filteredChunks.find((c) => c.key === selectedChunkKey) ?? filteredChunks[0] ?? null;
  const answerText = data.response || '';
  const chunksJson = JSON.stringify(liveChunks ?? [], null, 2);
  return (
    <div className="bottom-pane">
      <div className="bottom-pane-head">
        <span className="lane-tag">{label}</span>
        <div className="result-actions">
          <button type="button" className="result-action" onClick={() => copyText(answerText)}>Copy answer</button>
          <button type="button" className="result-action" onClick={() => copyText(chunksJson)}>Copy chunks</button>
        </div>
      </div>
      {isDemo && (
        <div style={{fontSize:10.5,color:'var(--warn)',fontFamily:'var(--font-mono)',margin:'0 0 6px',padding:'4px 6px',background:'var(--bg-card)',borderRadius:4}}>
          Demo data — not a live run. Execute the Usage lane for real retrieval & answer.
        </div>
      )}
      <div className="bottom-pane-stats">
        <span>{data.chunks} chunks</span>
        <span>{data.tokensIn} → {data.tokensOut} tok</span>
        <span>{data.durationMs}ms</span>
      </div>
      {view === 'llm' && (
        <>
          {data.plan && (
            <div style={{fontSize:10.5,color:'var(--text-dim)',fontFamily:'var(--font-mono)',marginBottom:6,padding:'4px 6px',background:'var(--bg-card)',borderRadius:4}}>
              <strong style={{color:'var(--text-muted)'}}>Plan:</strong> {data.plan.description}
              {' · '}
              {data.plan.tags.slice(0,5).map(t => (
                <span key={t.t} className="tag-pill" style={{fontSize:9.5,marginRight:2}}>{t.t} {t.w_query.toFixed(2)}</span>
              ))}
              {data.plan.tags.length > 5 && <span style={{color:'var(--text-dim)'}}> +{data.plan.tags.length-5} more</span>}
            </div>
          )}
          {rInput && (
            <div style={{fontSize:10,color:'var(--text-dim)',fontFamily:'var(--font-mono)',marginBottom:6,padding:'4px 6px',background:'var(--bg-card)',borderRadius:4}}>
              <strong style={{color:'var(--text-muted)'}}>Retrieval input:</strong>{' '}
              {rInput.scope.datasetId || 'all datasets'} · {rInput.scope.runId} · {rInput.controls.strategy}
              {' · '}
              limit {rInput.controls.limit} · k {rInput.controls.groundingK} · min_sim {Number(rInput.controls.minSim).toFixed(2)}
              {' · '}
              facets {rInput.controls.activeFacets.join(',') || 'none'} · gate {formatRetrievalGate(rInput.gate)}
            </div>
          )}
          {data.plan?.grounding?.length > 0 && (
            <div style={{fontSize:10,color:'var(--text-dim)',fontFamily:'var(--font-mono)',marginBottom:6,padding:'4px 6px',background:'var(--bg-card)',borderRadius:4}}>
              <strong style={{color:'var(--text-muted)'}}>Grounding:</strong>
              {data.plan.grounding.map(g => (
                <div key={g.promptTag} style={{marginTop:2}}>
                  {g.promptTag} →{' '}
                  {g.matches.length
                    ? g.matches.slice(0,4).map(m => (
                        <span key={`${m.name}:${m.facet}`} className="tag-pill" style={{fontSize:9.5,marginRight:2}}>{m.name}/{m.facet} {m.sim.toFixed(2)}</span>
                      ))
                    : <span style={{color:'var(--err)'}}>no match</span>}
                </div>
              ))}
            </div>
          )}
          <div className="bottom-pane-resp">{data.response}</div>
        </>
      )}
      {view === 'chunks' && (
        <div className="chunk-workbench">
          <div className="chunk-toolbar">
            <input value={chunkFilter} onChange={(e) => setChunkFilter(e.target.value)} placeholder="Filter evidence chunks…" />
            <span>{filteredChunks.length}/{normalizedChunks.length}</span>
          </div>
          <div className="chunk-layout">
            <div className="chunk-list">
              {filteredChunks.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={cls('chunk-row', selectedChunk?.key === c.key && 'active')}
                  onClick={() => setSelectedChunkKey(c.key)}
                >
                  <span className="chunk-row-score">{Number(c.score).toFixed(3)}</span>
                  <span className="chunk-row-text">{c.description || c.content}</span>
                  <span className="chunk-row-rel">{c.relevanceToFile != null ? Number(c.relevanceToFile).toFixed(2) : '—'}</span>
                </button>
              ))}
            </div>
            <div className="chunk-detail">
              {selectedChunk ? (
                <>
                  <div className="chunk-detail-head">
                    <span>{selectedChunk.key}</span>
                    <button type="button" className="result-action" onClick={() => copyText(selectedChunk.content)}>Copy chunk</button>
                  </div>
                  <div className="chunk-detail-meta">
                    file {selectedChunk.fileId} · score {Number(selectedChunk.score).toFixed(3)}
                    {selectedChunk.relevanceToFile != null && ` · rel ${Number(selectedChunk.relevanceToFile).toFixed(2)}`}
                  </div>
                  <pre className="chunk-detail-body">{selectedChunk.content}</pre>
                </>
              ) : (
                <div className="bottom-pane-empty">No chunks match the filter.</div>
              )}
            </div>
          </div>
        </div>
      )}
      {view === 'table' && (
        <div className="run-data-grid">
          <Metric label="chunks" value={data.chunks} />
          <Metric label="tokens in" value={data.tokensIn} />
          <Metric label="tokens out" value={data.tokensOut} />
          <Metric label="duration" value={`${data.durationMs}ms`} />
          <Metric label="dataset" value={rInput?.scope?.datasetId || 'sample'} />
          <Metric label="strategy" value={rInput?.controls?.strategy || 'sample'} />
          <Metric label="facets" value={rInput?.controls?.activeFacets?.join(', ') || 'none'} wide />
          <Metric label="gate" value={formatRetrievalGate(rInput?.gate)} wide />
          {data.plan && <Metric label="plan tags" value={data.plan.tags.length} />}
          {data.plan?.grounding && <Metric label="grounded tags" value={data.plan.grounding.reduce((n, g) => n + g.matches.length, 0)} />}
        </div>
      )}
      {data.topFacets?.length > 0 && (
        <div className="tag-row" style={{marginTop:4}}>
          {data.topFacets.map(c => <span key={c} className="tag-pill" data-facet={c}>{c}</span>)}
        </div>
      )}
    </div>
  );
}

// ─── Mount ──────────────────────────────────────────────────────────────────
function Metric({ label, value, wide = false }) {
  return (
    <div className={cls('metric-cell', wide && 'wide')}>
      <div className="metric-label">{label}</div>
      <div className="metric-value" title={String(value ?? '')}>{value ?? '—'}</div>
    </div>
  );
}

function LogPanel({ events, pipelineError, onClearLog }) {
  return (
    <div className="bottom-console">
      <div className="console-toolbar">
        <span>{events.length} events</span>
        {pipelineError && <span className="console-error">{pipelineError}</span>}
        <button type="button" className="result-action" onClick={onClearLog}>Clear</button>
      </div>
      <div className="log-list">
        {events.length ? events.slice().reverse().map((ev) => (
          <div key={ev.id} className={cls('log-row', ev.status)}>
            <span className="log-time">{ev.at}</span>
            <span className="log-status">{ev.status}</span>
            <span className="log-stage">{ev.stage}</span>
            <span className="log-message">{ev.message}</span>
          </div>
        )) : (
          <div className="bottom-pane-empty">No log events yet.</div>
        )}
      </div>
    </div>
  );
}

// ─── Run Builder ────────────────────────────────────────────────────────────
function RunSpecField({ spec, field, route, datasetOptions, queryModules, onChange }) {
  const value = specGet(spec, field.path);
  const active = leverActive(field, route);
  const set = (v) => onChange(specSet(spec, field.path, v));
  const baseStyle = { opacity: active ? 1 : 0.4 };
  const ctl = (el) => (
    <label className="run-field" style={baseStyle} title={active ? '' : `Inert for the "${route}" route — that node is bypassed.`}>
      <span className="run-field-label">{field.label}</span>
      {el}
    </label>
  );
  if (field.kind === 'select') {
    // The `models` option is rendered as <optgroup>s by provider so the user
    // can see at a glance which provider (and therefore which env key) each
    // model needs. Other selects are flat lists.
    if (field.options === 'models') {
      const byProvider = new Map();
      for (const m of MODELS) {
        if (!byProvider.has(m.provider)) byProvider.set(m.provider, []);
        byProvider.get(m.provider).push(m);
      }
      return ctl(
        <select value={value ?? ''} disabled={!active} onChange={(e) => set(e.target.value)}>
          {[...byProvider.entries()].map(([prov, list]) => (
            <optgroup key={prov} label={PROVIDERS[prov].label}>
              {list.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </optgroup>
          ))}
        </select>,
      );
    }
    const opts = field.options === 'routes' ? RUN_ROUTES.map((r) => [r.id, r.label])
      : field.options === 'answerModes' ? RUN_ANSWER_MODES.map((m) => [m.id, m.label])
        : field.options === 'databases' ? RUN_DATABASES.map((d) => [d, d])
          : [];
    return ctl(
      <select value={value ?? ''} disabled={!active} onChange={(e) => set(e.target.value)}>
        {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>,
    );
  }
  if (field.kind === 'dataset') {
    return ctl(
      <select value={value ?? ''} disabled={!active} onChange={(e) => set(e.target.value || null)}>
        <option value="">all datasets</option>
        {datasetOptions.map((d) => <option key={d.id} value={d.id}>{d.id}</option>)}
      </select>,
    );
  }
  if (field.kind === 'module') {
    return ctl(
      <select value={value ?? ''} disabled={!active} onChange={(e) => set(e.target.value || null)}>
        <option value="">— none —</option>
        {queryModules.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
      </select>,
    );
  }
  if (field.kind === 'facets') {
    return (
      <div className="run-field" style={baseStyle}>
        <span className="run-field-label">{field.label}</span>
        <div className="run-facets">
          {FACETS.map((f) => {
            const on = Array.isArray(value) && value.includes(f.id);
            return (
              <button
                key={f.id} type="button" disabled={!active}
                className={cls('tag-pill', on && 'active')}
                onClick={() => set(on ? value.filter((x) => x !== f.id) : [...(value || []), f.id])}
              >{f.id}</button>
            );
          })}
        </div>
      </div>
    );
  }
  // int / float / text
  const isNum = field.kind === 'int' || field.kind === 'float';
  return ctl(
    <input
      type={isNum ? 'number' : 'text'}
      value={value ?? ''}
      disabled={!active}
      min={field.min}
      step={field.step ?? (field.kind === 'int' ? 1 : undefined)}
      onChange={(e) => {
        if (!isNum) return set(e.target.value);
        const n = field.kind === 'int' ? parseInt(e.target.value, 10) : parseFloat(e.target.value);
        set(Number.isFinite(n) ? n : 0);
      }}
    />,
  );
}

function RunSpecCard({
  spec, index, datasetOptions, queryModules, onChange, onDuplicate, onRemove, removable,
  ragasSaveSubdir, setRagasExportStatus,
}) {
  const moduleRoute = spec.route === 'module';
  return (
    <div className="run-card">
      <div className="run-card-head">
        <input
          className="run-card-title"
          value={spec.label}
          onChange={(e) => onChange(specSet(spec, 'label', e.target.value))}
        />
        <span className="run-card-route">{spec.route} · {spec.database}</span>
        <div className="result-actions">
          <button
            type="button"
            className="result-action"
            onClick={() => exportRagasConfig(spec, ragasSaveSubdir, setRagasExportStatus)}
            disabled={moduleRoute}
            title={moduleRoute
              ? 'Module route is not supported by the headless RAGAS exporter'
              : `Save RunSpec JSON under ${RAGAS_EXPORTS_DIR}/ for ragas:export --config`}
          >
            Export RAGAS run
          </button>
          <button type="button" className="result-action" onClick={onDuplicate}>Duplicate</button>
          <button type="button" className="result-action" disabled={!removable} onClick={onRemove}>Remove</button>
        </div>
      </div>
      {RUN_LEVERS.map((group) => {
        const gActive = groupActive(group, spec.route);
        return (
          <div key={group.node} className="run-group" style={{ opacity: gActive ? 1 : 0.45 }}>
            <div className="run-group-node" title={`Levers owned by the "${group.node}" node`}>{group.label}</div>
            <div className="run-group-fields">
              {group.fields.map((f) => (
                <RunSpecField
                  key={f.path} spec={spec} field={f} route={spec.route}
                  datasetOptions={datasetOptions} queryModules={queryModules}
                  onChange={onChange}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CompareRunsView({ runResults, view }) {
  if (!runResults.length) {
    return <div className="bottom-pane-empty">No runs executed yet. Configure runs above and press “Run all”.</div>;
  }
  const ok = runResults.filter((r) => !r.error && r.retrievedChunks);
  const overlap = ok.length > 1 ? compareRuns(ok) : null;
  return (
    <div>
      {overlap && overlap.pairs.length > 0 && (
        <div className="run-overlap">
          <strong>Chunk overlap</strong>
          {overlap.pairs.map((p) => (
            <span key={`${p.a}|${p.b}`} className="tag-pill" title="shared retrieved chunks · Jaccard">
              {p.a} ∩ {p.b}: {p.count} · J={p.jaccard.toFixed(2)}
            </span>
          ))}
        </div>
      )}
      <div className="bottom-body run-compare">
        {runResults.map((r) => (
          r.error
            ? (
              <div key={r.specId} className="bottom-pane">
                <div className="bottom-pane-head"><span className="lane-tag">{r.label}</span></div>
                <div style={{ fontSize: 11, color: 'var(--err)', fontFamily: 'var(--font-mono)', padding: 8 }}>
                  Run failed ({r.route} · {r.database}): {r.error}
                </div>
              </div>
            )
            : <ResultPane key={r.specId} label={`${r.label} — ${r.route} · ${r.database}`} tone="full" data={r} view={view}/>
        ))}
      </div>
    </div>
  );
}

function RagasSaveToField({ subdir, setSubdir, status }) {
  return (
    <label className="run-export-dir" title={`Files are written under ${RAGAS_EXPORTS_DIR}/ at the repo root (dev server only)`}>
      <span className="run-export-dir-label">Save to</span>
      <span className="run-export-dir-prefix mono">{RAGAS_EXPORTS_DIR}/</span>
      <input
        className="run-export-dir-input mono"
        value={subdir}
        onChange={(e) => setSubdir(e.target.value.replace(/\\/g, '/').replace(/^\/+/, ''))}
        placeholder="(optional subfolder)"
      />
      {status && <span className="run-export-dir-status mono">{status}</span>}
    </label>
  );
}

function RunBuilderPanel({
  prompt, runSpecs, setRunSpecs, runResults, runsBusy, onRunAll,
  datasetOptions, queryModules, outputView,
  ragasSaveSubdir, setRagasSaveSubdir, ragasExportStatus, setRagasExportStatus,
}) {
  const update = (id, nextSpec) => setRunSpecs((s) => s.map((x) => (x.id === id ? nextSpec : x)));
  const duplicate = (spec) => setRunSpecs((s) => {
    const i = s.findIndex((x) => x.id === spec.id);
    const copy = { ...JSON.parse(JSON.stringify(spec)), id: uid('spec'), label: `${spec.label} (copy)` };
    return [...s.slice(0, i + 1), copy, ...s.slice(i + 1)];
  });
  const remove = (id) => setRunSpecs((s) => (s.length > 1 ? s.filter((x) => x.id !== id) : s));
  const add = () => setRunSpecs((s) => [...s, makeDefaultRunSpec({ model: s[0]?.answer.model || 'claude-haiku-4-5' }, `run ${s.length + 1}`, 'tags')]);

  return (
    <div className="bottom-console run-builder">
      <div className="console-toolbar">
        <button type="button" className="result-action" disabled={runsBusy} onClick={onRunAll}>
          {runsBusy ? 'Running…' : `Run all (${runSpecs.length})`}
        </button>
        <button type="button" className="result-action" disabled={runsBusy} onClick={add}>Add run</button>
        <RagasSaveToField
          subdir={ragasSaveSubdir}
          setSubdir={setRagasSaveSubdir}
          status={ragasExportStatus}
        />
        <span className="console-muted">same prompt across all runs: “{prompt}”</span>
      </div>
      <div className="run-cards">
        {runSpecs.map((spec, i) => (
          <RunSpecCard
            key={spec.id} spec={spec} index={i}
            datasetOptions={datasetOptions} queryModules={queryModules}
            removable={runSpecs.length > 1}
            ragasSaveSubdir={ragasSaveSubdir}
            setRagasExportStatus={setRagasExportStatus}
            onChange={(next) => update(spec.id, next)}
            onDuplicate={() => duplicate(spec)}
            onRemove={() => remove(spec.id)}
          />
        ))}
      </div>
      <CompareRunsView runResults={runResults} view={outputView} />
    </div>
  );
}

function HistoryPanel({ runs, prompt, onRestoreRun, ragasSaveSubdir, setRagasExportStatus }) {
  return (
    <div className="bottom-console">
      <div className="console-toolbar">
        <span>{runs.length} runs</span>
        <span className="console-muted">current prompt: {prompt}</span>
        <button
          type="button"
          className="result-action"
          disabled={!runs.some((r) => r.results || (r.kind === 'run' && r.runResult))}
          onClick={() => exportRagasJsonl(runs, ragasSaveSubdir, setRagasExportStatus)}
          title={`Save successful runs as JSONL under ${RAGAS_EXPORTS_DIR}/`}
        >
          Export RAGAS
        </button>
      </div>
      <div className="history-list">
        {runs.length ? runs.map((run) => (
          <button
            key={run.id}
            type="button"
            className={cls('history-row', run.status)}
            onClick={() => onRestoreRun(run)}
            disabled={!run.results && run.kind !== 'run'}
          >
            <span className="history-status">{run.status}</span>
            <span className="history-main">
              <span className="history-prompt">{run.prompt}</span>
              <span className="history-meta">
                {run.kind === 'run'
                  ? `run "${run.spec?.label}" · ${run.spec?.route} · ${run.spec?.database} · ${run.durationMs}ms · ${run.chunksA} chunks`
                  : `${run.datasetId || 'all'} · ${run.durationMs}ms · A ${run.chunksA} chunks · B ${run.chunksB} chunks`}
                {run.error && ` · ${run.error}`}
              </span>
            </span>
            <span className="history-time">{run.at}</span>
          </button>
        )) : (
          <div className="bottom-pane-empty">No completed runs yet.</div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState('workbench'); // 'workbench' | 'ragas'
  if (view === 'ragas') {
    return <RagasReportPage onBack={() => setView('workbench')} />;
  }
  return (
    <ReactFlowProvider>
      <WorkbenchApp onOpenReports={() => setView('ragas')} />
    </ReactFlowProvider>
  );
}
