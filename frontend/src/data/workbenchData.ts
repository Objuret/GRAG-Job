/**
 * Workbench node registry + the small demo set used only for the pre-run
 * placeholder (PRESET_RESULTS / SAMPLE_CHUNKS, shown behind an explicit
 * "Demo data" banner). All live numbers come from the real run, not here.
 */

import type { FacetDimension } from '../types';

// ─── Pipeline lane: defines what's in the graph ─────────────────────────────
export const PIPELINE_NODES = [
  { id: 'dataset',   label: 'Dataset',      sub: 'HERB',         inType: null,          outType: 'source',      icon: 'Ds', color: 'var(--type-source)',  lane: 'pipeline' },
  { id: 'access',    label: 'Access Layer', sub: 'files',        inType: 'source',      outType: 'files',       icon: 'Ac', color: 'var(--type-files)',   lane: 'pipeline' },
  { id: 'index',     label: 'Index Layer',  sub: 'graph',        inType: 'files',       outType: 'graph',       icon: 'Ix', color: 'var(--type-chunks)',  lane: 'pipeline' },
  { id: 'tags',      label: 'Tags',         sub: 'HAS_TAG',      inType: 'graph',       outType: 'graph_scope', icon: 'Tg', color: 'var(--type-tags)',    lane: 'pipeline' },
  { id: 'facets',    label: 'Facets',       sub: 'view',         inType: 'graph_scope', outType: 'graph_scope', icon: 'Fa', color: 'var(--type-tags)',    lane: 'pipeline' },
];

// ─── Usage lane: the real executable pipeline (one node = one executor) ──────
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

export const NODE_TYPES = [...PIPELINE_NODES, ...USAGE_NODES, ...MODULE_NODES];

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

export const DATASETS = [
  { id: 'Salesforce__HERB', files: 33, chunks: 5843, tags: 25896 },
  { id: 'fever__feverous', files: 0, chunks: 0, tags: 0 },
  { id: 'VLR-CVC__DocVQA-2026', files: 0, chunks: 0, tags: 0 },
  { id: 'wenhu__hybrid_qa', files: 0, chunks: 0, tags: 0 },
];

export const SAMPLE_CHUNKS = [
  { id: 'c_a001_000', file: 'f_a001', preview: 'Revenue for Q2 showed a 12% increase year-over-year, driven primarily by expansion into new market segments.', rel: 0.92,
    tags: [
      { name: 'revenue_analysis', facet: 'topic', w: 0.85 },
      { name: 'q2_2025', facet: 'temporal', w: 0.91 },
      { name: 'quarterly_report', facet: 'activity', w: 0.72 },
    ]},
  { id: 'c_a001_001', file: 'f_a001', preview: 'The product launch in the Nordic region exceeded initial projections by 34%. Customer acquisition cost decreased to $47 per unit.', rel: 0.78,
    tags: [
      { name: 'market_expansion', facet: 'topic', w: 0.78 },
      { name: 'product_launch', facet: 'activity', w: 0.65 },
      { name: 'acme_corp', facet: 'entities', w: 0.92 },
    ]},
  { id: 'c_a001_002', file: 'f_a001', preview: 'Year-to-date performance against targets: revenue at 108%, retention at 94%, NPS improved from 42 to 51.', rel: 0.85,
    tags: [
      { name: 'performance_metric', facet: 'topic', w: 0.88 },
      { name: 'comparison', facet: 'evidence', w: 0.74 },
    ]},
  { id: 'c_a003_000', file: 'f_a003', preview: 'This annual overview consolidates findings from all twelve data batches processed during the evaluation period.', rel: 0.95,
    tags: [
      { name: 'annual_summary', facet: 'topic', w: 0.93 },
      { name: 'historical', facet: 'temporal', w: 0.70 },
    ]},
  { id: 'c_b001_000', file: 'f_b001', preview: '{"entity_id":"ENT-0042","type":"organisation","label":"Demo Systems Inc","sector":"technology","status":"active"}', rel: 0.60,
    tags: [
      { name: 'demo_systems_inc', facet: 'entities', w: 0.95 },
      { name: 'active', facet: 'temporal', w: 0.50 },
    ]},
];

/**
 * Demo lane comparison text shown before the first real run. The UI labels
 * this as demo data (ResultPane "Demo data" banner) and replaces it wholesale
 * once the Usage lane runs the real pipeline.
 */
export const PRESET_RESULTS = {
  full: {
    response: 'Q2 revenue rose 12% year-over-year, driven by Nordic market expansion (product launch +34% vs projection) and operating margins improved 2.2pp. Year-to-date performance is at 108% of revenue target with retention at 94%. The annual overview confirms these trends sit within a broader pattern of operational efficiency gains.',
    chunks: 47, tokensIn: 1247, tokensOut: 312, durationMs: 2840,
    topFacets: ['topic', 'activity', 'temporal'],
  },
  baseline: {
    response: 'The data mentions a 12% revenue increase in Q2 and a product launch in the Nordic region. However, one retrieved record appears to be an unrelated entity record for a technology company, suggesting the retrieval precision could be improved.',
    chunks: 312, tokensIn: 1189, tokensOut: 287, durationMs: 2610,
    topFacets: [] as FacetDimension[],
  },
};
