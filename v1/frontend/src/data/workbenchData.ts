/** Workbench node registry and static catalog metadata. Live run output is never seeded here. */

// ─── Usage canvas: executable pipeline (one node = one executor) ────────────
// These kinds map 1:1 to executors in services/pipeline.ts. Wire order is run
// order; A/B is a real fork (retrieve_tags vs retrieve_baseline) joined at
// `compare`.
export const USAGE_NODES = [
  { id: 'prompt',            label: 'Prompt',       sub: 'user query',     inType: null,             outType: 'prompt',          icon: 'Pr', color: 'var(--type-prompt)', lane: 'usage' },
  { id: 'interpret',         label: 'Interpret',    sub: '2-pass LLM',     inType: 'prompt',         outType: 'query_plan',      icon: 'In', color: 'var(--type-interp)', lane: 'usage' },
  { id: 'build_input',       label: 'Build input',  sub: 'scope+gate',     inType: 'query_plan',     outType: 'retrieval_input', icon: 'Bi', color: 'var(--type-interp)', lane: 'usage' },
  { id: 'ground',            label: 'Ground',       sub: 'e5 + kNN',       inType: 'retrieval_input',outType: 'grounded',        icon: 'Gr', color: 'var(--type-tags)',   lane: 'usage' },
  { id: 'retrieve_tags',     label: 'Retrieve A',   sub: 'HERB tags',      inType: 'grounded',       outType: 'chunks',          icon: 'Ra', color: 'var(--type-chunks)', lane: 'usage' },
  { id: 'retrieve_baseline', label: 'Retrieve B',   sub: 'baseline',       inType: 'retrieval_input',outType: 'chunks',          icon: 'Rb', color: 'var(--type-chunks)', lane: 'usage' },
  { id: 'answer',            label: 'Answer',       sub: 'LLM over chunks',inType: 'chunks',         outType: 'answer',          icon: 'An', color: 'var(--type-result)', lane: 'usage' },
  { id: 'compare',           label: 'Compare',      sub: 'A/B + metrics',  inType: 'answer',         outType: 'result',          icon: 'Cm', color: 'var(--type-result)', lane: 'usage' },
];

// ─── Modules: type-safe inserts you can splice into any matching wire ────────
export const MODULE_NODES = [
  { id: 'probe', label: 'Probe / test', sub: 'passthrough', inType: 'any', outType: 'any', icon: 'Pb', color: 'var(--neutral)', lane: 'module' },
];

export const NODE_TYPES = [...USAGE_NODES, ...MODULE_NODES];

/** Inner template fragments (chain with frag → frag inside a Query module). `qf_start` is auto-seeded, not in the catalog. */
export const QUERY_FRAGMENT_NODES = [
  { id: 'qf_start',            label: 'Start',            sub: 'entry',         inType: null,  outType: 'frag', icon: '▸', color: 'var(--type-interp)',  lane: 'fragment' },
  { id: 'qf_topic',            label: 'Topic slice',      sub: 'template',    inType: 'frag', outType: 'frag', icon: 'To', color: 'var(--type-tags)',   lane: 'fragment' },
  { id: 'qf_entities',         label: 'Entities',         sub: 'template',    inType: 'frag', outType: 'frag', icon: 'En', color: 'var(--type-tags)',   lane: 'fragment' },
  { id: 'qf_activity',         label: 'Activity',         sub: 'template',    inType: 'frag', outType: 'frag', icon: 'Ac', color: 'var(--type-tags)',   lane: 'fragment' },
  { id: 'qf_temporal',         label: 'Temporal',         sub: 'template',    inType: 'frag', outType: 'frag', icon: 'Tm', color: 'var(--type-tags)',   lane: 'fragment' },
  { id: 'qf_evidence',         label: 'Evidence',         sub: 'template',    inType: 'frag', outType: 'frag', icon: 'Ev', color: 'var(--type-tags)',   lane: 'fragment' },
] as const;

/** Catalog only: facet template blocks (excludes internal `qf_start`). */
export const QUERY_FRAGMENT_CATALOG = QUERY_FRAGMENT_NODES.filter((n) => n.id !== 'qf_start');

/** Draggable shell: drop creates a `queryGroup` + seeded `qf_start` (xyflow type `queryGroup`). */
export const QUERY_CONTAINER = {
  id: 'queryContainer',
  label: 'Query module',
  sub: 'retrieval_plan -> graph query',
  inType: 'retrieval_plan' as const,
  outType: 'retrieval_plan' as const,
  icon: 'Qy',
  color: 'var(--type-query)',
};

export const TYPE_LABEL: Record<string, string> = {
  source: 'source:Dataset', files: 'files:AccessLayer', graph: 'graph:Neo4j',
  graph_scope: 'graph:FacetScope',
  prompt: 'prompt:Query', query_plan: 'plan:Interpreted',
  retrieval_input: 'input:Retrieval', grounded: 'input:Grounded',
  chunks: 'chunks:Retrieved', answer: 'answer:LLM', result: 'result:A/B',
  any: 'any:Passthrough',
  retrieval_plan: 'plan:Retrieval', context: 'chunks:Retrieved',
  frag: 'frag:TemplateStep',
};

export const FACETS = [
  { id: 'topic',     label: 'Topic',    hint: 'What is this about?' },
  { id: 'entities',  label: 'Entities', hint: 'Which concrete things are named or referenced?' },
  { id: 'activity',  label: 'Activity', hint: 'What kind of event, process, or content action is described?' },
  { id: 'temporal',  label: 'Temporal', hint: 'When is this relevant: recent, historical, future, active, completed?' },
  { id: 'evidence',  label: 'Evidence', hint: 'What kind of answer material is supplied?' },
];

// ─── Run Builder: every lever, mapped to the node that owns it ──────────────
// A Run is a config snapshot of the Usage graph. The UI renders one section
// per node so each lever is shown under the node it belongs to (this is the
// "understand what a node stands for" requirement made literal in the form).

export const RUN_ROUTES = [
  { id: 'tags',      label: 'Tags — graph retrieval (the artefact)',     node: 'retrieve_tags' },
  { id: 'baseline',  label: 'Baseline — relevance-ordered, gated',        node: 'retrieve_baseline' },
  { id: 'content',   label: 'Content — Lucene full-text on raw chunks',   node: 'retrieve_baseline' },
  { id: 'module',    label: 'Query module — composed Cypher',             node: 'querymodule' },
  { id: 'sql_agent', label: 'SQL agent — LLM with SQL tool over HERB DB', node: 'sql_agent' },
] as const;

export const RUN_ANSWER_MODES = [
  { id: 'context', label: 'context (structured, default)' },
  { id: 'raw',     label: 'raw (prompt only)' },
  { id: 'hybrid',  label: 'hybrid' },
] as const;

export const RUN_DATABASES = ['herb-eval', 'herb'] as const;

/** Compare node: which lanes, panel views, metric blocks, and export rows to include. */
export const DEFAULT_COMPARE_OUTPUT = {
  lanes: { a: true, b: true },
  views: { llm: true, chunks: true, table: true },
  metrics: {
    overlap: true,
    retrieval: true,
    grounding: true,
    citations: true,
    latency: true,
  },
  export: { laneA: true, laneB: true, includeMetrics: true },
};

export function normalizeCompareOutput(raw: unknown) {
  const d = (raw && typeof raw === 'object' ? raw : {}) as Partial<typeof DEFAULT_COMPARE_OUTPUT>;
  return {
    lanes: { a: d.lanes?.a !== false, b: d.lanes?.b !== false },
    views: {
      llm: d.views?.llm !== false,
      chunks: d.views?.chunks !== false,
      table: d.views?.table !== false,
    },
    metrics: {
      overlap: d.metrics?.overlap !== false,
      retrieval: d.metrics?.retrieval !== false,
      grounding: d.metrics?.grounding !== false,
      citations: d.metrics?.citations !== false,
      latency: d.metrics?.latency !== false,
    },
    export: {
      laneA: d.export?.laneA !== false,
      laneB: d.export?.laneB !== false,
      includeMetrics: d.export?.includeMetrics !== false,
    },
  };
}

/** Form schema: groups are nodes; each field carries the RunSpec path it
 *  binds and is greyed when the chosen route makes it inert. */
export const RUN_LEVERS = [
  { node: 'prompt', label: 'Prompt', fields: [
    { path: 'answer.mode', label: 'Answer mode', kind: 'select', options: 'answerModes' },
  ] },
  { node: 'interpret', label: 'Interpret', skipOnRoute: ['content', 'sql_agent'], fields: [
    { path: 'interpret.model', label: 'Model', kind: 'select', options: 'models' },
    { path: 'interpret.datasetId', label: 'Dataset', kind: 'dataset' },
  ] },
  { node: 'build_input', label: 'Build input', skipOnRoute: ['content', 'sql_agent'], fields: [
    { path: 'buildInput.maxChunks', label: 'Max chunks (0 = no limit)', kind: 'int', min: 0 },
    { path: 'buildInput.weightThreshold', label: 'Weight threshold (min_w_chunk)', kind: 'float', min: 0, step: 0.05 },
    { path: 'buildInput.minRelevanceToFile', label: 'Min relevance-to-file', kind: 'float', min: 0, step: 0.05 },
    { path: 'buildInput.groundingK', label: 'Grounding k (0 = no limit)', kind: 'int', min: 0, onlyRoute: ['tags', 'module'] },
    { path: 'buildInput.minSim', label: 'Min sim', kind: 'float', min: 0, step: 0.01, onlyRoute: ['tags', 'module'] },
    { path: 'buildInput.activeFacets', label: 'Active facets', kind: 'facets', onlyRoute: ['tags', 'module'] },
    { path: 'buildInput.runId', label: 'Run id', kind: 'text' },
  ] },
  { node: 'route', label: 'Route', fields: [
    { path: 'route', label: 'Retrieval route', kind: 'select', options: 'routes' },
    { path: 'moduleId', label: 'Query module', kind: 'module', onlyRoute: ['module'] },
  ] },
  { node: 'answer', label: 'Answer', fields: [
    { path: 'answer.model', label: 'Model', kind: 'select', options: 'models' },
    { path: 'temperature', label: 'Temperature (interpret + answer)', kind: 'float', min: 0, step: 0.1 },
  ] },
  { node: 'neo4j', label: 'Database', fields: [
    { path: 'database', label: 'Neo4j database', kind: 'select', options: 'databases' },
  ] },
  { node: 'sql_agent', label: 'SQL agent', onlyOnRoute: ['sql_agent'], fields: [
    { path: 'sqlAgent.maxToolCalls', label: 'Max SQL calls (0 = no limit)', kind: 'int', min: 0 },
    { path: 'sqlAgent.maxRowsPerQuery', label: 'Max rows per query (0 = no limit)', kind: 'int', min: 0 },
    { path: 'sqlAgent.maxCellChars', label: 'Max chars per cell (0 = no limit)', kind: 'int', min: 0 },
  ] },
] as const;

export const DATASETS = [
  { id: 'Salesforce__HERB', files: 33, chunks: 4869, tags: 24781 },
  { id: 'fever__feverous', files: 0, chunks: 0, tags: 0 },
  { id: 'VLR-CVC__DocVQA-2026', files: 0, chunks: 0, tags: 0 },
  { id: 'wenhu__hybrid_qa', files: 0, chunks: 0, tags: 0 },
];
