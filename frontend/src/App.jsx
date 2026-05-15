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
  PIPELINE_NODES, USAGE_NODES, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS, SAMPLE_CHUNKS,
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
import { interpretPrompt } from './services/interpreter';
import { retrieveChunks, retrieveBaseline } from './services/retrieval';
import { generateAnswer } from './services/answer';
import { fetchDatasetStats } from './services/neo4j';
const NT = Object.fromEntries([...NODE_TYPES, ...QUERY_FRAGMENT_NODES].map((n) => [n.id, n]));

const DONE_GRAPH_DATABASE = 'herb';
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
  const payload = STAGE_PAYLOADS[t.id] || {};
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
        {t.id !== 'output' && t.id !== 'dataset' && t.id !== 'prompt' && t.id !== 'qf_start' && (
          <div className={cls('node-toggle', !data.disabled && 'on')}
               onClick={(e) => { e.stopPropagation(); data.onToggle?.(); }} />
        )}
      </div>
      <div className="node-body">
        <div className="node-row">
          <span className="label">in</span>
          <span className="val">{payload.inCount ?? '—'}</span>
        </div>
        <div className="node-row">
          <span className="label">out</span>
          <span className="val">{data.disabled ? '—' : (payload.outCount ?? '—')}</span>
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
      <div className="query-group-hint">Plan in · step order = query order · candidates out</div>
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
function buildInitial() {
  const pipelineOrder = PIPELINE_NODES.map(n => n.id);  // dataset, access, index, tags, clusters
  const usageOrder    = USAGE_NODES.map(n => n.id);     // prompt, interpreter, graphquery, retrieval, output

  const xStart = 32, xGap = 260, yInner = 72;
  const maxCols = Math.max(pipelineOrder.length, usageOrder.length);
  // Reserve room for the last stage (184px wide) + matching right margin so it doesn't kiss the lane edge.
  const laneW = xStart + (maxCols - 1) * xGap + 184 + 32;
  const laneH = 244;
  const laneGap = 56;

  const lanes = [
    { id: 'lane_pipeline', label: 'Pipeline — graph construction', y: 0,              order: pipelineOrder },
    { id: 'lane_usage',    label: 'Usage — query & retrieval',     y: laneH + laneGap, order: usageOrder },
  ];

  const nodes = [];
  const edges = [];

  for (const lane of lanes) {
    nodes.push({
      id: lane.id, type: 'lane', position: { x: 0, y: lane.y },
      style: { width: laneW, height: laneH, zIndex: -1 },
      data: { label: lane.label, lastRun: null, running: false, lockContent: true },
      draggable: true, selectable: true,
    });
    const stageNodes = lane.order.map((kind, i) => ({
      id: `${lane.id}_${kind}`, type: 'stage',
      position: { x: xStart + i * xGap, y: yInner },
      parentId: lane.id, extent: 'parent',
      data: { kind, disabled: false, running: false },
    }));
    nodes.push(...stageNodes);
    for (let i = 0; i < stageNodes.length - 1; i++) {
      const conn = {
        source: stageNodes[i].id,
        target: stageNodes[i + 1].id,
        sourceHandle: 'h-right-a',
        targetHandle: 'h-left-a',
      };
      const ok = connectionContractOk(conn, nodes);
      edges.push({
        id: `e_${stageNodes[i].id}__${stageNodes[i + 1].id}`,
        ...conn,
        type: 'default',
        animated: false,
        className: ok ? undefined : 'invalid',
        data: {
          type: NT[lane.order[i]].outType,
          fromKind: lane.order[i],
          toKind: lane.order[i + 1],
          contractOk: ok,
        },
      });
    }
  }

  // Empty Query module, seeded but not wired to the lanes — gives a clear starting surface
  // for fragment drops without making cross-lane wiring assumptions on first paint.
  const qgW = 620;
  const qgH = 320;
  const qgX = Math.max(0, Math.round((laneW - qgW) / 2));
  const qgY = 2 * laneH + laneGap + 72;
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
const defaultConnConfig = {
  neo4jUri:       (typeof import.meta !== 'undefined' && import.meta.env?.VITE_NEO4J_URI)        || 'bolt://localhost:7687',
  neo4jUser:      (typeof import.meta !== 'undefined' && import.meta.env?.VITE_NEO4J_USER)       || 'neo4j',
  neo4jPassword:  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_NEO4J_PASSWORD)   || '',
  neo4jDatabase:  DONE_GRAPH_DATABASE,
  openaiApiKey:   (typeof import.meta !== 'undefined' && import.meta.env?.VITE_OPENAI_API_KEY)   || '',
  anthropicApiKey:(typeof import.meta !== 'undefined' && import.meta.env?.VITE_ANTHROPIC_API_KEY)|| '',
  model:          (typeof import.meta !== 'undefined' && import.meta.env?.VITE_MODEL)            || 'claude-haiku-4-5',
};

function normalizeConnConfig(cfg = {}) {
  return { ...defaultConnConfig, ...(cfg || {}), neo4jDatabase: DONE_GRAPH_DATABASE };
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

function fmtCount(v) {
  return typeof v === 'number' ? v.toLocaleString() : '0';
}

// ─── App ───────────────────────────────────────────────────────────────────
function WorkbenchApp() {
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
  const [config, setConfig]     = useState({
    dataset: DATASETS[0]?.id || 'Salesforce__HERB',
    clusters: { topic: true, entities: true, activity: true, temporal: true, evidence: true },
    canonicalOnly: false, weightThreshold: 0.0, maxChunks: 50, formatFilter: 'All',
  });
  const [outputView, setOutputView] = useState('llm');   // llm | chunks | table
  const connConfig = useMemo(() => normalizeConnConfig(), []);
  const [datasetOptions, setDatasetOptions] = useState(DATASETS);
  const [datasetLoadState, setDatasetLoadState] = useState({ loading: false, error: null, source: 'fallback' });
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineError, setPipelineError] = useState(null);

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
      schedule(700, () => finishLane(720 + Math.floor(Math.random() * 120)));
      return;
    }

    const failAt =
      order.length > 1 && Math.random() < 0.07
        ? 1 + Math.floor(Math.random() * (order.length - 1))
        : -1;

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
        const base = 80 + order.length * (D_EDGE + D_NODE + D_GAP);
        finishLane(base + Math.floor(Math.random() * 450));
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

        if (failAt === i) {
          setNodes((nds) => nds.map((n) => {
            if (n.id === laneId) return { ...n, data: { ...n.data, running: false, lastRun: null } };
            if (n.id === stageId && stages.has(n.id))
              return { ...n, data: { ...n.data, execPhase: 'failed' } };
            return n;
          }));
          return;
        }

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
        const options = toDatasetOptions(stats);
        setDatasetOptions(options);
        setDatasetLoadState({ loading: false, error: null, source: stats.length ? 'graph' : 'fallback' });
        setConfig((prev) => (
          options.some((d) => d.id === prev.dataset) ? prev : { ...prev, dataset: options[0]?.id || DATASETS[0]?.id }
        ));
      })
      .catch((err) => {
        if (!live) return;
        setDatasetOptions(DATASETS);
        setDatasetLoadState({ loading: false, error: err?.message || String(err), source: 'fallback' });
        setConfig((prev) => (
          DATASETS.some((d) => d.id === prev.dataset) ? prev : { ...prev, dataset: DATASETS[0]?.id || 'Salesforce__HERB' }
        ));
      });

    return () => { live = false; };
  }, [connConfig.neo4jUri, connConfig.neo4jUser, connConfig.neo4jPassword]);

  const runPipeline = useCallback(async () => {
    const needsOpenAI = !connConfig.model.startsWith('claude');
    const activeKey = needsOpenAI ? connConfig.openaiApiKey : connConfig.anthropicApiKey;
    if (!activeKey) {
      const which = needsOpenAI ? 'OpenAI' : 'Anthropic';
      setPipelineError(`${which} API key not set in Vite env.`);
      return;
    }
    setPipelineRunning(true);
    setPipelineError(null);
    const t0 = Date.now();
    try {
      const datasetId = config.dataset || datasetOptions[0]?.id || DATASETS[0]?.id || null;
      const neo4jCfg = {
        uri: connConfig.neo4jUri,
        user: connConfig.neo4jUser,
        password: connConfig.neo4jPassword,
        database: DONE_GRAPH_DATABASE,
      };
      const plan = await interpretPrompt(prompt, connConfig.model, connConfig.openaiApiKey, connConfig.anthropicApiKey, datasetId);
      const [chunks, bChunks] = await Promise.all([
        retrieveChunks(plan, neo4jCfg),
        retrieveBaseline(plan.filters.limit, neo4jCfg, datasetId),
      ]);
      const [ansA, ansB] = await Promise.all([
        generateAnswer(prompt, plan, chunks, connConfig.model, connConfig.openaiApiKey, connConfig.anthropicApiKey),
        generateAnswer(prompt, plan, bChunks, connConfig.model, connConfig.openaiApiKey, connConfig.anthropicApiKey),
      ]);
      const topFacets = [...new Set(
        plan.tags.flatMap(t => Object.entries(t.facets).filter(([, v]) => v >= 0.5).map(([k]) => k))
      )].slice(0, 4);
      const elapsed = Date.now() - t0;
      setResults({
        lane_A: {
          chunks: chunks.length, response: ansA.response,
          tokensIn: ansA.tokensIn, tokensOut: ansA.tokensOut, durationMs: elapsed,
          topClusters: topFacets, plan, retrievedChunks: chunks,
        },
        lane_B: {
          chunks: bChunks.length, response: ansB.response,
          tokensIn: ansB.tokensIn, tokensOut: ansB.tokensOut, durationMs: elapsed,
          topClusters: [], plan: null, retrievedChunks: bChunks,
        },
      });
    } catch (err) {
      setPipelineError(err?.message || String(err));
    } finally {
      setPipelineRunning(false);
    }
  }, [prompt, connConfig, config.dataset, datasetOptions]);

  const runLaneWithActualWork = useCallback((laneId) => {
    runLane(laneId);
    if (laneId === 'lane_usage') runPipeline();
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
      data = { type: 'query_plan', fromKind: s?.data?.kind ?? '', toKind: 'queryGroup', contractOk };
    } else if (s?.type === 'queryGroup' && t?.type === 'stage') {
      data = { type: 'candidates', fromKind: 'queryGroup', toKind: t?.data?.kind ?? '', contractOk };
    } else if (s?.type === 'stage' && t?.type === 'stage') {
      const sKind = NT[s.data.kind], tKind = NT[t.data.kind];
      if (s.data?.kind === 'clusters' && t.data?.kind === 'graphquery') {
        data = { type: 'ranked', fromKind: 'clusters', toKind: 'graphquery', contractOk };
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
      runLane('lane_pipeline');
      runLane('lane_usage');
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
    lanes.forEach((id) => runLane(id));
  }, [runLane]);

  const runAll = useCallback(() => {
    runLane('lane_pipeline');
    runLane('lane_usage');
    runPipeline();
  }, [runLane, runPipeline]);

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
  const selPayload = selKind ? STAGE_PAYLOADS[selKind.id] : null;
  const selEdge = edgeSel && edges.find(e => e.id === edgeSel);

  return (
    <div className={cls('workbench', edgeSel && 'drawer-open')}>
      <TopStrip {...{ theme, setTheme, prompt, setPrompt, runAll, pipelineRunning }}/>
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
        <Inspector selKind={selKind} selNode={selNode} selPayload={selPayload}
                   config={config} setConfig={setConfig}
                   datasetOptions={datasetOptions} datasetLoadState={datasetLoadState}
                   prompt={prompt} setPrompt={setPrompt}
                   outputView={outputView} setOutputView={setOutputView}
                   queryContainerMeta={QUERY_CONTAINER}
                   nodes={nodes}
                   edges={edges}
                   patchNodeData={patchNodeData} />
        {selEdge && <Drawer edge={selEdge} nodes={nodes} onClose={() => setEdgeSel(null)} />}
      </div>
      <BottomPanel results={results} prompt={prompt} outputView={outputView} setOutputView={setOutputView}
                   pipelineRunning={pipelineRunning} pipelineError={pipelineError}/>
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
function TopStrip({ theme, setTheme, prompt, setPrompt, runAll, pipelineRunning }) {
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
        <div className="catalog-hint">Graph construction: dataset → indexed, tagged, clustered.</div>
        <div className="catalog-list">{renderList(PIPELINE_NODES)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Usage</h4>
        <div className="catalog-hint">Query & retrieval: prompt → interpret → query graph → rank → LLM output.</div>
        <div className="catalog-list">{renderList(USAGE_NODES)}</div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Query module</h4>
        <div className="catalog-hint">Query module: interpreter plan → any <strong>qin</strong> face; <strong>qout</strong> → retrieval. Ports appear on each side; extras on the same edge spread out. Arrows always run from source drag to target drop. Invalid pairs stay linked but draw red.</div>
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
              Left handle brings in the interpreter&apos;s structured <strong>plan</strong>. Inner nodes are steps—left-to-right chain is the order those steps apply. Right handle sends <strong>candidate chunks</strong> to Retrieval. The GUI shows what each step <em>means</em>; Cypher is optional detail under Technical.
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
function Inspector({ selKind, selNode, selPayload, config, setConfig, datasetOptions, datasetLoadState, prompt, setPrompt, outputView, setOutputView, queryContainerMeta, nodes, edges, patchNodeData }) {
  const [tab, setTab] = useState('config');
  if (!selNode) {
    return (
      <aside className="inspector">
        <div className="insp-empty">
          <div>
            <div className="insp-empty-glyph">{I.inspect}</div>
            <div className="insp-empty-title">Nothing selected</div>
            <div className="insp-empty-sub">Click a node to inspect config, live counts and sample I/O. Click an edge to see the payload that flows across it.</div>
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
        {['config','io','tags','runtime'].map(t => (
          <button key={t} className={cls('insp-tab', tab === t && 'active')} onClick={() => setTab(t)}>
            {t === 'config' ? 'Config' : t === 'io' ? 'I/O' : t === 'tags' ? 'Tags' : 'Runtime'}
          </button>
        ))}
      </div>
      <div className="insp-body">
        {tab === 'config' && (
          <ConfigForm
            kind={selKind.id}
            config={config}
            setConfig={setConfig}
            datasetOptions={datasetOptions}
            datasetLoadState={datasetLoadState}
            prompt={prompt}
            setPrompt={setPrompt}
            outputView={outputView}
            setOutputView={setOutputView}
            syntaxCtx={{ selNode, nodes, edges, patchNodeData }}
          />
        )}
        {tab === 'io' && <IOPanel selKind={selKind} selPayload={selPayload}/>}
        {tab === 'tags' && <TagsPanel selPayload={selPayload}/>}
        {tab === 'runtime' && <RuntimePanel selPayload={selPayload}/>}
      </div>
    </aside>
  );
}

function ConfigForm({ kind, config, setConfig, datasetOptions, datasetLoadState, prompt, setPrompt, outputView, setOutputView, syntaxCtx }) {
  const set = (patch) => setConfig({ ...config, ...patch });
  if (kind === 'prompt') {
    return (
      <>
        <div className="field">
          <label className="field-label">Prompt context<span className="hint">shared across lanes</span></label>
          <textarea className="field-textarea" value={prompt} onChange={(e) => setPrompt(e.target.value)}/>
        </div>
        <div className="field">
          <label className="field-label">Mode<span className="hint">how the prompt is built</span></label>
          <select className="field-select" defaultValue="context">
            <option value="context">Build prompt context (api-mode)</option>
            <option value="raw">Raw prompt only</option>
            <option value="hybrid">Hybrid: context + system</option>
          </select>
        </div>
      </>
    );
  }
  if (kind === 'dataset') {
    const options = datasetOptions?.length ? datasetOptions : DATASETS;
    const ds = options.find(d => d.id === config.dataset) || options[0];
    const datasetValue = ds?.id || '';
    return (
      <>
        <div className="field">
          <label className="field-label">Source<span className="hint">:Source node in graph</span></label>
          <select className="field-select" value={datasetValue} onChange={(e) => set({ dataset: e.target.value })}>
            {options.map(d => <option key={d.id} value={d.id}>{d.id}</option>)}
          </select>
          {datasetLoadState?.error && (
            <div className="tweaks-hint" style={{ marginTop: 6 }}>Using raw dataset list; Neo4j source lookup is unavailable.</div>
          )}
          {datasetLoadState?.loading && (
            <div className="tweaks-hint" style={{ marginTop: 6 }}>Loading graph sources...</div>
          )}
        </div>
        <div className="stat-grid">
          <div className="stat-card"><div className="stat-card-label">Files</div><div className="stat-card-val">{fmtCount(ds?.files)}</div></div>
          <div className="stat-card"><div className="stat-card-label">Chunks</div><div className="stat-card-val">{fmtCount(ds?.chunks)}</div></div>
          <div className="stat-card"><div className="stat-card-label">Tags</div><div className="stat-card-val">{fmtCount(ds?.tags)}</div></div>
          <div className="stat-card"><div className="stat-card-label">Adapter</div><div className="stat-card-val" style={{fontSize:11}}>neo4j_driver</div></div>
        </div>
      </>
    );
  }
  if (kind === 'access') {
    return (
      <>
        <div className="field">
          <label className="field-label">Format filter</label>
          <select className="field-select" value={config.formatFilter} onChange={(e) => set({ formatFilter: e.target.value })}>
            {['All','json','jsonl','parquet','yaml','pdf','html','docx','txt'].map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label">Min description length<span className="hint">filter sparse files</span></label>
          <input className="field-input" type="number" defaultValue="0"/>
        </div>
      </>
    );
  }
  if (kind === 'index') {
    return (
      <>
        <div className="field">
          <label className="field-label">Max chunks<span className="hint">cap retrieval depth</span></label>
          <input className="field-input" type="number" value={config.maxChunks} onChange={(e) => set({ maxChunks: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Strategy</label>
          <select className="field-select" defaultValue="dense">
            <option value="dense">Dense vector (default)</option>
            <option value="bm25">BM25</option>
            <option value="hybrid">Hybrid (dense + BM25)</option>
          </select>
        </div>
      </>
    );
  }
  if (kind === 'tags') {
    return (
      <>
        <div className="field">
          <label className="field-label">Active cluster dimensions</label>
          <div className="cluster-grid">
            {CLUSTERS.map(c => (
              <div key={c.id} className={cls('cluster-chip', config.clusters[c.id] && 'on')}
                   title={c.hint}
                   onClick={() => set({ clusters: { ...config.clusters, [c.id]: !config.clusters[c.id] } })}>
                <span className="cluster-chip-dot"/>{c.label}
              </div>
            ))}
          </div>
        </div>
        <div className="field">
          <label className="field-label">Weight threshold<span className="hint">{config.weightThreshold.toFixed(2)}</span></label>
          <input className="field-input" type="range" min="0" max="1" step="0.05"
                 value={config.weightThreshold}
                 onChange={(e) => set({ weightThreshold: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Canonical tags only</label>
          <select className="field-select" value={config.canonicalOnly ? 'yes' : 'no'} onChange={(e) => set({ canonicalOnly: e.target.value === 'yes' })}>
            <option value="no">No — include proposals</option>
            <option value="yes">Yes — canonical only</option>
          </select>
        </div>
      </>
    );
  }
  if (kind === 'clusters') {
    return (
      <>
        <div className="field">
          <label className="field-label">Active cluster dimensions</label>
          <div className="cluster-grid">
            {CLUSTERS.map(c => (
              <div key={c.id} className={cls('cluster-chip', config.clusters[c.id] && 'on')}
                   title={c.hint}
                   onClick={() => set({ clusters: { ...config.clusters, [c.id]: !config.clusters[c.id] } })}>
                <span className="cluster-chip-dot"/>{c.label}
              </div>
            ))}
          </div>
        </div>
        <div className="field">
          <label className="field-label">Ranking method</label>
          <select className="field-select" defaultValue="weighted">
            <option value="weighted">Weighted sum across clusters</option>
            <option value="max">Max weight per cluster</option>
            <option value="hybrid">Hybrid (weighted + relevance)</option>
          </select>
        </div>
      </>
    );
  }
  if (kind === 'interpreter') {
    return (
      <>
        <div className="field">
          <label className="field-label">Interpreter model<span className="hint">analyses the prompt</span></label>
          <select className="field-select" defaultValue="claude-haiku-4-5">
            <option>claude-haiku-4-5</option>
            <option>claude-sonnet-4-5</option>
            <option>claude-opus-4-6</option>
            <option>gpt-4o-mini</option>
            <option>gpt-4o</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">Strategy<span className="hint">how to map prompt to graph terms</span></label>
          <select className="field-select" defaultValue="tag_extraction">
            <option value="tag_extraction">Extract tags from prompt</option>
            <option value="embedding_match">Embedding similarity to canonical tags</option>
            <option value="hybrid">Hybrid (tags + embedding)</option>
          </select>
        </div>
      </>
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
  if (kind === 'graphquery') {
    return (
      <>
        <div className="field">
          <label className="field-label">Query strategy<span className="hint">how to traverse the graph</span></label>
          <select className="field-select" defaultValue="tag_match">
            <option value="tag_match">Tag match (Cypher)</option>
            <option value="vector">Vector similarity</option>
            <option value="hybrid">Hybrid (tag + vector)</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">Max candidates<span className="hint">pre-ranking cap</span></label>
          <input className="field-input" type="number" value={config.maxChunks} onChange={(e) => set({ maxChunks: +e.target.value })}/>
        </div>
        <div className="field">
          <label className="field-label">Cluster filter<span className="hint">which dimensions to query</span></label>
          <div className="cluster-grid">
            {CLUSTERS.map(c => (
              <div key={c.id} className={cls('cluster-chip', config.clusters[c.id] && 'on')}
                   title={c.hint}
                   onClick={() => set({ clusters: { ...config.clusters, [c.id]: !config.clusters[c.id] } })}>
                <span className="cluster-chip-dot"/>{c.label}
              </div>
            ))}
          </div>
        </div>
      </>
    );
  }
  if (kind === 'retrieval') {
    return (
      <>
        <div className="field">
          <label className="field-label">Ranking method<span className="hint">how to score candidates</span></label>
          <select className="field-select" defaultValue="weighted">
            <option value="weighted">Weighted sum across clusters</option>
            <option value="rrf">Reciprocal Rank Fusion</option>
            <option value="relevance">Relevance-to-file only</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">Top-K<span className="hint">chunks sent to LLM</span></label>
          <input className="field-input" type="number" defaultValue="50"/>
        </div>
        <div className="field">
          <label className="field-label">Weight threshold<span className="hint">{config.weightThreshold.toFixed(2)}</span></label>
          <input className="field-input" type="range" min="0" max="1" step="0.05"
                 value={config.weightThreshold}
                 onChange={(e) => set({ weightThreshold: +e.target.value })}/>
        </div>
      </>
    );
  }
  if (kind === 'output') {
    return (
      <>
        <div className="field">
          <label className="field-label">LLM model<span className="hint">for final answer</span></label>
          <select className="field-select" defaultValue="claude-haiku-4-5">
            <option>claude-haiku-4-5</option>
            <option>claude-sonnet-4-5</option>
            <option>claude-opus-4-6</option>
            <option>gpt-4o-mini</option>
            <option>gpt-4o</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">View mode<span className="hint">controls bottom panel</span></label>
          <select className="field-select" value={outputView} onChange={(e) => setOutputView(e.target.value)}>
            <option value="llm">LLM Response</option>
            <option value="chunks">Raw Chunks</option>
            <option value="table">Table</option>
          </select>
        </div>
      </>
    );
  }
  return <div style={{fontSize:11,color:'var(--text-muted)'}}>No configuration.</div>;
}

function IOPanel({ selKind, selPayload }) {
  const p = selPayload || {};
  return (
    <>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-card-label">Records in</div><div className="stat-card-val">{p.inCount ?? '—'}</div><div className="stat-card-sub">{selKind.inType || 'no input'}</div></div>
        <div className="stat-card"><div className="stat-card-label">Records out</div><div className="stat-card-val">{p.outCount ?? '—'}</div><div className="stat-card-sub">{selKind.outType || 'no output'}</div></div>
      </div>
      <div className="section-head">Sample output</div>
      <div className="sample-table">
        <div className="sample-row head"><span className="col col-id">id</span><span className="col">preview</span><span className="col col-w">w</span></div>
        {(p.sample || []).map((r,i) => (
          <div key={i} className="sample-row">
            <span className="col col-id">{r.id}</span>
            <span className="col" title={r.val}>{r.val}</span>
            <span className="col col-w">{r.w}</span>
          </div>
        ))}
      </div>
    </>
  );
}

function TagsPanel({ selPayload }) {
  const samples = (selPayload?.sample || []).slice(0,3);
  return (
    <>
      <div className="section-head">Top tags by cluster</div>
      {CLUSTERS.map(c => {
        const tags = SAMPLE_CHUNKS.flatMap(ch => ch.tags).filter(t => t.cluster === c.id).slice(0,4);
        if (tags.length === 0) return null;
        return (
          <div key={c.id}>
            <div style={{fontSize:10.5,color:'var(--text-dim)',fontFamily:'var(--font-mono)',marginBottom:4}}>{c.label}</div>
            <div className="tag-row">
              {tags.map((t,i) => <span key={i} className="tag-pill" data-cluster={t.cluster}>{t.name} · {t.w.toFixed(2)}</span>)}
            </div>
          </div>
        );
      })}
    </>
  );
}

function RuntimePanel({ selPayload }) {
  return (
    <>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-card-label">Last run</div><div className="stat-card-val">412ms</div></div>
        <div className="stat-card"><div className="stat-card-label">Adapter</div><div className="stat-card-val" style={{fontSize:11}}>neo4j_driver v5</div></div>
        <div className="stat-card"><div className="stat-card-label">Cypher hits</div><div className="stat-card-val">{selPayload?.outCount ?? '—'}</div></div>
        <div className="stat-card"><div className="stat-card-label">Cache</div><div className="stat-card-val" style={{fontSize:11,color:'var(--ok)'}}>warm</div></div>
      </div>
      <div className="section-head">Recent log</div>
      <div className="sample-table">
        <div className="sample-row"><span className="col col-id" style={{color:'var(--text-dim)'}}>10:42:12</span><span className="col">Connected to bolt://neo4j-mock</span><span className="col col-w" style={{color:'var(--ok)'}}>OK</span></div>
        <div className="sample-row"><span className="col col-id" style={{color:'var(--text-dim)'}}>10:42:13</span><span className="col">MATCH (s:Source)…</span><span className="col col-w" style={{color:'var(--ok)'}}>312</span></div>
        <div className="sample-row"><span className="col col-id" style={{color:'var(--text-dim)'}}>10:42:13</span><span className="col">payload serialised</span><span className="col col-w" style={{color:'var(--ok)'}}>OK</span></div>
      </div>
    </>
  );
}

// ─── Edge Drawer ────────────────────────────────────────────────────────────
function Drawer({ edge, nodes, onClose }) {
  const sNode = nodes.find(n => n.id === edge.source);
  const tNode = nodes.find(n => n.id === edge.target);
  const sKind = sNode?.type === 'queryGroup'
    ? { label: 'Query module', outType: 'candidates', inType: null, id: 'queryGroup' }
    : (sNode?.data?.kind ? NT[sNode.data.kind] : null);
  const tKind = tNode?.type === 'queryGroup'
    ? { label: 'Query module', outType: null, inType: 'query_plan', id: 'queryGroup' }
    : (tNode?.data?.kind ? NT[tNode.data.kind] : null);
  const payloadKindId = sNode?.type === 'queryGroup' ? null : sKind?.id;
  const payload = payloadKindId ? STAGE_PAYLOADS[payloadKindId] : null;
  return (
    <aside className="drawer">
      <div className="drawer-head">
        <span className="drawer-head-pill">{I.link} edge</span>
        <div className="drawer-title">Payload on the wire</div>
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
        <div className="stat-grid">
          <div className="stat-card"><div className="stat-card-label">Records</div><div className="stat-card-val">{payload?.outCount ?? '—'}</div><div className="stat-card-sub">{edge.data?.type}</div></div>
          <div className="stat-card"><div className="stat-card-label">Latency</div><div className="stat-card-val">~12ms</div><div className="stat-card-sub">serialise + relay</div></div>
        </div>
        <div className="section-head">Sample payload</div>
        <div className="sample-table">
          <div className="sample-row head"><span className="col col-id">id</span><span className="col">preview</span><span className="col col-w">w</span></div>
          {(payload?.sample || []).map((r,i) => (
            <div key={i} className="sample-row">
              <span className="col col-id">{r.id}</span>
              <span className="col" title={r.val}>{r.val}</span>
              <span className="col col-w">{r.w}</span>
            </div>
          ))}
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
    case 'chunks':
    case 'tagged':
    case 'ranked':
    case 'candidates':
    case 'context':    return [{name:'chunkId',type:'string'},{name:'fileId',type:'string'},{name:'content',type:'text'},{name:'tags[]',type:'ChunkTag'},{name:'weight',type:'float'}];
    case 'query_plan': return [{name:'extractedTags',type:'string[]'},{name:'clusters',type:'ClusterDimension[]'},{name:'strategy',type:'enum'}];
    case 'frag':       return [{name:'slotId',type:'string'},{name:'boundParams',type:'Record<string, unknown>'}];
    case 'result':     return [{name:'llmResponse',type:'string'},{name:'tokensIn',type:'int'},{name:'tokensOut',type:'int'},{name:'durationMs',type:'int'}];
    default: return [];
  }
}

// ─── Bottom Panel (lane comparison) ─────────────────────────────────────────
function BottomPanel({ results, prompt, outputView, setOutputView, pipelineRunning, pipelineError }) {
  const a = results.lane_A, b = results.lane_B;
  return (
    <section className="bottom">
      <div className="bottom-head">
        <div className="bottom-tab active">{I.layers} Lane Comparison</div>
        <div className="bottom-tab" style={{opacity:.6}}>Logs</div>
        <div className="bottom-tab" style={{opacity:.6}}>Run history</div>
        <div style={{flex:1}}/>
        {pipelineRunning && (
          <span style={{fontSize:11,color:'var(--accent)',marginRight:12,animation:'pulse 1.2s infinite'}}>
            {I.zap} Running pipeline…
          </span>
        )}
        {pipelineError && !pipelineRunning && (
          <span style={{fontSize:11,color:'var(--err)',marginRight:12,maxWidth:320,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}
                title={pipelineError}>
            ⚠ {pipelineError}
          </span>
        )}
        <div className="bottom-pane-mode">
          {[['llm','LLM'],['chunks','Chunks'],['table','Table']].map(([k,l]) =>
            <button key={k} className={cls(outputView === k && 'active')} onClick={() => setOutputView(k)}>{l}</button>)}
        </div>
      </div>
      <div className="bottom-body">
        <ResultPane label="Lane A — HERB tags" tone="full" data={a} view={outputView}/>
        <ResultPane label="Lane B — baseline (no tags)" tone="baseline" data={b} view={outputView}/>
      </div>
    </section>
  );
}
function ResultPane({ label, tone, data, view }) {
  if (!data) return <div className="bottom-pane"><div className="bottom-pane-empty">Run the lane to see results.</div></div>;
  const liveChunks = data.retrievedChunks;
  return (
    <div className="bottom-pane">
      <div className="bottom-pane-head">
        <span className="lane-tag">{label}</span>
      </div>
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
          <div className="bottom-pane-resp">{data.response}</div>
        </>
      )}
      {view === 'chunks' && (
        <div className="sample-table">
          <div className="sample-row head">
            <span className="col col-id">score</span>
            <span className="col">description / content</span>
            <span className="col col-w">rel</span>
          </div>
          {(liveChunks ?? SAMPLE_CHUNKS.slice(0, tone === 'full' ? 4 : 5)).map((c, i) => {
            const isLive = !!liveChunks;
            const preview = isLive ? (c.description || c.content || '').slice(0, 90) : c.preview;
            const score   = isLive ? c.score?.toFixed(3) : c.rel?.toFixed(2);
            const rel     = isLive ? (c.relevanceToFile?.toFixed(2) ?? '—') : c.rel?.toFixed(2);
            const title   = isLive ? (c.content || '') : c.preview;
            return (
              <div key={i} className="sample-row">
                <span className="col col-id">{score}</span>
                <span className="col" title={title}>{preview}</span>
                <span className="col col-w">{rel}</span>
              </div>
            );
          })}
        </div>
      )}
      {view === 'table' && (
        <div className="sample-table">
          <div className="sample-row head"><span className="col col-id">metric</span><span className="col">value</span><span className="col col-w"></span></div>
          <div className="sample-row"><span className="col col-id">chunks</span><span className="col">{data.chunks}</span><span className="col col-w"></span></div>
          <div className="sample-row"><span className="col col-id">tokens in</span><span className="col">{data.tokensIn}</span><span className="col col-w"></span></div>
          <div className="sample-row"><span className="col col-id">tokens out</span><span className="col">{data.tokensOut}</span><span className="col col-w"></span></div>
          <div className="sample-row"><span className="col col-id">duration</span><span className="col">{data.durationMs}ms</span><span className="col col-w"></span></div>
          {data.plan && <div className="sample-row"><span className="col col-id">plan tags</span><span className="col">{data.plan.tags.length}</span><span className="col col-w"></span></div>}
        </div>
      )}
      {data.topClusters?.length > 0 && (
        <div className="tag-row" style={{marginTop:4}}>
          {data.topClusters.map(c => <span key={c} className="tag-pill" data-cluster={c}>{c}</span>)}
        </div>
      )}
    </div>
  );
}

// ─── Mount ──────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <ReactFlowProvider>
      <WorkbenchApp />
    </ReactFlowProvider>
  );
}
