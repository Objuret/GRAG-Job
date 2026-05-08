// Antigrav Workbench — main app (React + xyflow via ESM)
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow, ReactFlowProvider, useNodesState, useEdgesState,
  addEdge, Background, Controls, MiniMap, Handle, Position, NodeResizer,
  BaseEdge, getBezierPath, EdgeLabelRenderer, useReactFlow,
} from '@xyflow/react';

// ─── Tweak defaults (persisted via __edit_mode_set_keys) ──────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "defaultTheme": "dark",
  "showMinimap": true,
  "showEdgeLabels": true,
  "animatedEdges": false,
  "accentColor": "#b189ff",
  "laneGap": 40,
  "defaultTopK": 50
}/*EDITMODE-END*/;

import { NODE_TYPES, TYPE_LABEL, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS, SAMPLE_CHUNKS } from './data/mockData';
const NT = Object.fromEntries(NODE_TYPES.map(n => [n.id, n]));

// ─── helpers ───────────────────────────────────────────────────────────────
const cls = (...xs) => xs.filter(Boolean).join(' ');
const uid = (p) => `${p}_${Math.random().toString(36).slice(2,8)}`;
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
};

// ─── Stage Node component (xyflow custom node) ─────────────────────────────
const StageNode = React.memo(({ data, selected }) => {
  const t = NT[data.kind];
  if (!t) return null;
  const payload = STAGE_PAYLOADS[t.id] || {};
  const cap = data.disabled ? 'unavailable' : (data.running ? 'running' : 'runnable');
  return (
    <div className={cls('node-stage', selected && 'selected', data.disabled && 'disabled')}
         style={{ '--node-accent': t.color }}>
      <div className="node-accent" />
      {t.inType && <Handle type="target" position={Position.Left} id="in" />}
      {t.outType && <Handle type="source" position={Position.Right} id="out" />}
      <div className="node-head">
        <div className="node-head-icon">{t.icon}</div>
        <div>
          <div className="node-title">{t.label}</div>
          <div className="node-subtitle">{t.sub}</div>
        </div>
        {t.id !== 'output' && t.id !== 'dataset' && t.id !== 'prompt' && (
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
const LaneNode = React.memo(({ data, selected }) => {
  return (
    <>
      <NodeResizer minWidth={600} minHeight={220} isVisible={selected} />
      <div className={cls('node-lane', selected && 'selected')}>
        <div className="lane-header">
          <input className="lane-name" defaultValue={data.label || 'Lane'}
                 onPointerDown={(e) => e.stopPropagation()}
                 onChange={(e) => data.onRename?.(e.target.value)} />
          <span className="lane-status">
            <span className={cls('cap-dot', data.running ? 'running' : 'runnable')} />
            {data.running ? 'running…' : (data.lastRun ? `${data.lastRun}ms` : 'ready')}
          </span>
          <div className="lane-actions">
            <button className={cls('lane-run', data.running && 'running')}
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

const nodeTypes = { stage: StageNode, lane: LaneNode };

// ─── Initial canvas: two parallel lanes for A/B ────────────────────────────
function buildInitial() {
  const order = ['prompt','dataset','access','index','tags','clusters','output'];
  const xStart = 24, xGap = 200, y = 56;
  const laneW = xStart + order.length * xGap + 24;
  const laneH = 220;

  const lanes = [
    { id: 'lane_A', label: 'Lane A — full pipeline', y: 0, disabled: {} },
    { id: 'lane_B', label: 'Lane B — tags OFF (baseline)', y: laneH + 40, disabled: { tags: true } },
  ];

  const nodes = [];
  const edges = [];

  for (const lane of lanes) {
    nodes.push({
      id: lane.id, type: 'lane', position: { x: 0, y: lane.y },
      style: { width: laneW, height: laneH, zIndex: -1 },
      data: { label: lane.label, lastRun: null, running: false },
      draggable: true, selectable: true,
    });
    const stageNodes = order.map((kind, i) => ({
      id: `${lane.id}_${kind}`, type: 'stage',
      position: { x: xStart + i * xGap, y: y },
      parentId: lane.id, extent: 'parent',
      data: { kind, disabled: !!lane.disabled[kind], running: false },
    }));
    nodes.push(...stageNodes);
    for (let i = 0; i < stageNodes.length - 1; i++) {
      edges.push({
        id: `e_${stageNodes[i].id}__${stageNodes[i+1].id}`,
        source: stageNodes[i].id, target: stageNodes[i+1].id,
        sourceHandle: 'out', targetHandle: 'in', type: 'smoothstep', animated: false,
        data: { type: NT[order[i]].outType, fromKind: order[i], toKind: order[i+1] },
      });
    }
  }
  return { nodes, edges };
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
    dataset: 'source_alpha_demo',
    clusters: { theme: true, object_entity: true, event_process: true, time_relevance: true, information_need: true },
    canonicalOnly: false, weightThreshold: 0.0, maxChunks: 50, formatFilter: 'All',
  });
  const [outputView, setOutputView] = useState('llm');   // llm | chunks | table

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

  // Wire callbacks into nodes (toggle, rename, run, etc.)
  const wiredNodes = useMemo(() => nodes.map(n => {
    if (n.type === 'lane') {
      return { ...n, data: { ...n.data,
        onRename: (v) => setNodes(nds => nds.map(x => x.id === n.id ? { ...x, data: { ...x.data, label: v } } : x)),
        onRun: () => runLane(n.id),
      }};
    }
    if (n.type === 'stage') {
      return { ...n, data: { ...n.data,
        onToggle: () => setNodes(nds => nds.map(x => x.id === n.id ? { ...x, data: { ...x.data, disabled: !x.data.disabled } } : x)),
      }};
    }
    return n;
  }), [nodes]);

  const onConnect = useCallback((c) => {
    setEdges(eds => addEdge({ ...c, type: 'smoothstep', animated: false }, eds));
  }, [setEdges]);

  const isValidConnection = useCallback(({ source, target, sourceHandle, targetHandle }) => {
    if (source === target) return false;
    const s = nodes.find(n => n.id === source);
    const t = nodes.find(n => n.id === target);
    if (!s || !t) return false;
    if (s.type !== 'stage' || t.type !== 'stage') return false;
    const sKind = NT[s.data.kind], tKind = NT[t.data.kind];
    if (!sKind?.outType || !tKind?.inType) return false;
    return sKind.outType === tKind.inType;
  }, [nodes]);

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
    // Convert pointer coords (screen space) into flow coords, then offset by
    // half the node's rendered size so the node spawns CENTERED on the pointer.
    const flowPos = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    const isLane = kind === 'lane';
    const w = isLane ? 720 : 184;   // matches CSS
    const h = isLane ? 240 : 116;
    const pos = { x: flowPos.x - w / 2, y: flowPos.y - h / 2 };
    if (isLane) {
      setNodes(nds => nds.concat({
        id: uid('lane'), type: 'lane', position: pos,
        style: { width: w, height: h, zIndex: -1 },
        data: { label: 'New Lane', lastRun: null, running: false },
      }));
    } else {
      setNodes(nds => nds.concat({
        id: uid(kind), type: 'stage', position: pos,
        data: { kind, disabled: false, running: false },
      }));
    }
  }, [setNodes, rf]);

  const runLane = (laneId) => {
    setNodes(nds => nds.map(n => n.id === laneId ? { ...n, data: { ...n.data, running: true } } : n));
    setTimeout(() => {
      setNodes(nds => nds.map(n => n.id === laneId
        ? { ...n, data: { ...n.data, running: false, lastRun: 2840 + Math.floor(Math.random()*400) } }
        : n));
    }, 1200);
  };

  const runAll = () => { runLane('lane_A'); runLane('lane_B'); };

  // ─── Inspector content ──────────────────────────────────────────────────
  const selNode = selected && nodes.find(n => n.id === selected.id);
  const selKind = selNode?.data?.kind ? NT[selNode.data.kind] : null;
  const selPayload = selKind ? STAGE_PAYLOADS[selKind.id] : null;
  const selEdge = edgeSel && edges.find(e => e.id === edgeSel);

  return (
    <div className={cls('workbench', edgeSel && 'drawer-open')}>
      <TopStrip {...{ theme, setTheme, prompt, setPrompt, runAll }}/>
      <div className={cls('workbench-main', edgeSel && 'drawer-open')}>
        <Catalog />
        <div className="canvas" onDrop={onDrop} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}>
          <ReactFlow
            nodes={wiredNodes}
            edges={edges.map(e => ({
              ...e,
              animated: tweaks.animatedEdges,
              label: tweaks.showEdgeLabels ? (TYPE_LABEL[e.data?.type] || '') : '',
              labelStyle: { fontSize: 10 }, labelBgStyle: { fill: 'var(--bg-panel)' },
              labelBgPadding: [4,2], labelBgBorderRadius: 3
            }))}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            fitView fitViewOptions={{ padding: 0.18 }}
            proOptions={{ hideAttribution: true }}
            minZoom={0.4} maxZoom={1.6}
            selectionOnDrag panOnDrag={[1,2]} panOnScroll
            defaultEdgeOptions={{ type: 'smoothstep' }}
          >
            <Background gap={20} size={1.4} />
            <Controls position="bottom-right" showInteractive={false} />
            {tweaks.showMinimap && <MiniMap pannable zoomable nodeColor={(n) => n.type === 'lane' ? 'var(--bg-surface)' : (NT[n.data?.kind]?.color || 'var(--neutral)')} maskColor="rgba(0,0,0,.4)" />}
          </ReactFlow>
        </div>
        <Inspector selKind={selKind} selNode={selNode} selPayload={selPayload}
                   config={config} setConfig={setConfig}
                   prompt={prompt} setPrompt={setPrompt}
                   outputView={outputView} setOutputView={setOutputView} />
        {selEdge && <Drawer edge={selEdge} nodes={nodes} onClose={() => setEdgeSel(null)} />}
      </div>
      <BottomPanel results={results} prompt={prompt} outputView={outputView} setOutputView={setOutputView}/>
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
        <TwToggle label="Edge labels"      value={tweaks.showEdgeLabels} onChange={v => setTweak('showEdgeLabels', v)}/>
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
function TopStrip({ theme, setTheme, prompt, setPrompt, runAll }) {
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
      <button className="btn btn-primary" onClick={runAll}>{I.play} Execute All</button>
    </div>
  );
}

// ─── Catalog ────────────────────────────────────────────────────────────────
function Catalog() {
  const [q, setQ] = useState('');
  const filtered = NODE_TYPES.filter(n => !q || n.label.toLowerCase().includes(q.toLowerCase()) || n.id.includes(q.toLowerCase()));
  const onDragStart = (e, kind) => {
    e.dataTransfer.setData('application/ag-kind', kind);
    e.dataTransfer.effectAllowed = 'move';
  };
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
        <h4>Pipeline Nodes</h4>
        <div className="catalog-list">
          {filtered.map(n => (
            <div key={n.id} className="catalog-item" draggable onDragStart={(e) => onDragStart(e, n.id)}>
              <div className="catalog-item-icon" style={{ background: n.color }}>{n.icon}</div>
              <div>
                <div className="catalog-item-name">{n.label}</div>
                <div className="catalog-item-type">{n.inType || '—'} → {n.outType || '—'}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="catalog-divider" />
      <div className="catalog-section">
        <h4>Lanes</h4>
        <div className="catalog-hint">Drag a Lane onto the canvas to create a new runnable A/B branch. Lanes can contain another lane for nested testing.</div>
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
      <div className="catalog-hint">Tip: connections only join compatible types — invalid drops will be rejected.</div>
    </aside>
  );
}

// ─── Inspector ──────────────────────────────────────────────────────────────
function Inspector({ selKind, selNode, selPayload, config, setConfig, prompt, setPrompt, outputView, setOutputView }) {
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
        {tab === 'config' && <ConfigForm kind={selKind.id} config={config} setConfig={setConfig} prompt={prompt} setPrompt={setPrompt} outputView={outputView} setOutputView={setOutputView}/>}
        {tab === 'io' && <IOPanel selKind={selKind} selPayload={selPayload}/>}
        {tab === 'tags' && <TagsPanel selPayload={selPayload}/>}
        {tab === 'runtime' && <RuntimePanel selPayload={selPayload}/>}
      </div>
    </aside>
  );
}

function ConfigForm({ kind, config, setConfig, prompt, setPrompt, outputView, setOutputView }) {
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
    const ds = DATASETS.find(d => d.id === config.dataset) || DATASETS[0];
    return (
      <>
        <div className="field">
          <label className="field-label">Source<span className="hint">:Source node in graph</span></label>
          <select className="field-select" value={config.dataset} onChange={(e) => set({ dataset: e.target.value })}>
            {DATASETS.map(d => <option key={d.id} value={d.id}>{d.id}</option>)}
          </select>
        </div>
        <div className="stat-grid">
          <div className="stat-card"><div className="stat-card-label">Files</div><div className="stat-card-val">{ds.files}</div></div>
          <div className="stat-card"><div className="stat-card-label">Chunks</div><div className="stat-card-val">{ds.chunks}</div></div>
          <div className="stat-card"><div className="stat-card-label">Tags</div><div className="stat-card-val">{ds.tags}</div></div>
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
          <label className="field-label">Ranking method</label>
          <select className="field-select" defaultValue="weighted">
            <option value="weighted">Weighted sum across clusters</option>
            <option value="max">Max weight per cluster</option>
            <option value="hybrid">Hybrid (weighted + relevance)</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">Top-K</label>
          <input className="field-input" type="number" defaultValue="50"/>
        </div>
        <div className="field">
          <label className="field-label">Cluster contribution</label>
          <div className="cluster-grid">
            {CLUSTERS.map(c => (
              <div key={c.id} className={cls('cluster-chip', config.clusters[c.id] && 'on')}>
                <span className="cluster-chip-dot"/>{c.label}
              </div>
            ))}
          </div>
        </div>
      </>
    );
  }
  if (kind === 'output') {
    return (
      <>
        <div className="field">
          <label className="field-label">View mode<span className="hint">controls bottom panel</span></label>
          <select className="field-select" value={outputView} onChange={(e) => setOutputView(e.target.value)}>
            <option value="llm">LLM Response</option>
            <option value="chunks">Raw Chunks</option>
            <option value="table">Table</option>
          </select>
        </div>
        <div className="field">
          <label className="field-label">LLM model</label>
          <select className="field-select" defaultValue="gpt-4o-mini">
            <option>gpt-4o-mini</option>
            <option>llama-3.1-70b</option>
            <option>claude-3.5-sonnet</option>
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
  const sKind = sNode?.data?.kind ? NT[sNode.data.kind] : null;
  const tKind = tNode?.data?.kind ? NT[tNode.data.kind] : null;
  const payload = sKind ? STAGE_PAYLOADS[sKind.id] : null;
  return (
    <aside className="drawer">
      <div className="drawer-head">
        <span className="drawer-head-pill">{I.link} edge</span>
        <div className="drawer-title">Payload on the wire</div>
        <button className="btn btn-ghost btn-icon" onClick={onClose}>{I.close}</button>
      </div>
      <div className="drawer-body">
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
    case 'prompt': return [{name:'context',type:'string'},{name:'mode',type:'enum'}];
    case 'source': return [{name:'datasetId',type:'string'},{name:'fileCount',type:'int'},{name:'chunkCount',type:'int'}];
    case 'files':  return [{name:'fileId',type:'string'},{name:'relPath',type:'string'},{name:'formatFamily',type:'string'}];
    case 'chunks':
    case 'tagged':
    case 'ranked': return [{name:'chunkId',type:'string'},{name:'fileId',type:'string'},{name:'content',type:'text'},{name:'tags[]',type:'ChunkTag'},{name:'weight',type:'float'}];
    case 'result': return [{name:'llmResponse',type:'string'},{name:'tokensIn',type:'int'},{name:'tokensOut',type:'int'},{name:'durationMs',type:'int'}];
    default: return [];
  }
}

// ─── Bottom Panel (lane comparison) ─────────────────────────────────────────
function BottomPanel({ results, prompt, outputView, setOutputView }) {
  const a = results.lane_A, b = results.lane_B;
  return (
    <section className="bottom">
      <div className="bottom-head">
        <div className="bottom-tab active">{I.layers} Lane Comparison</div>
        <div className="bottom-tab" style={{opacity:.6}}>Logs</div>
        <div className="bottom-tab" style={{opacity:.6}}>Run history</div>
        <div style={{flex:1}}/>
        <div className="bottom-pane-mode">
          {[['llm','LLM'],['chunks','Chunks'],['table','Table']].map(([k,l]) =>
            <button key={k} className={cls(outputView === k && 'active')} onClick={() => setOutputView(k)}>{l}</button>)}
        </div>
      </div>
      <div className="bottom-body">
        <ResultPane label="Lane A" tone="full" data={a} view={outputView}/>
        <ResultPane label="Lane B" tone="baseline" data={b} view={outputView}/>
      </div>
    </section>
  );
}
function ResultPane({ label, tone, data, view }) {
  if (!data) return <div className="bottom-pane"><div className="bottom-pane-empty">Run the lane to see results.</div></div>;
  return (
    <div className="bottom-pane">
      <div className="bottom-pane-head">
        <span className="lane-tag">{label}</span>
        <span>tags {tone === 'full' ? 'ON' : 'OFF'} · clusters {tone === 'full' ? 'ON' : 'OFF'}</span>
      </div>
      <div className="bottom-pane-stats">
        <span>{data.chunks} chunks</span>
        <span>{data.tokensIn} → {data.tokensOut} tok</span>
        <span>{data.durationMs}ms</span>
      </div>
      {view === 'llm' && <div className="bottom-pane-resp">{data.response}</div>}
      {view === 'chunks' && (
        <div className="sample-table">
          <div className="sample-row head"><span className="col col-id">id</span><span className="col">preview</span><span className="col col-w">w</span></div>
          {SAMPLE_CHUNKS.slice(0, tone === 'full' ? 4 : 5).map((c,i) => (
            <div key={i} className="sample-row"><span className="col col-id">{c.id}</span><span className="col" title={c.preview}>{c.preview}</span><span className="col col-w">{c.rel.toFixed(2)}</span></div>
          ))}
        </div>
      )}
      {view === 'table' && (
        <div className="sample-table">
          <div className="sample-row head"><span className="col col-id">metric</span><span className="col">value</span><span className="col col-w">δ</span></div>
          <div className="sample-row"><span className="col col-id">precision</span><span className="col">{tone === 'full' ? '0.84' : '0.61'}</span><span className="col col-w pos">{tone === 'full' ? '+0.23' : ''}</span></div>
          <div className="sample-row"><span className="col col-id">recall</span><span className="col">{tone === 'full' ? '0.79' : '0.91'}</span><span className="col col-w" style={{color:'var(--err)'}}>{tone === 'full' ? '-0.12' : ''}</span></div>
          <div className="sample-row"><span className="col col-id">tokens</span><span className="col">{data.tokensIn + data.tokensOut}</span><span className="col col-w"></span></div>
        </div>
      )}
      {data.topClusters?.length > 0 && (
        <div className="tag-row">
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
