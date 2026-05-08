// Antigrav Workbench — mock data (synthetic only)
// Mirrors the structure in src/data/mockData.ts but tightened for the prototype.

window.AG = window.AG || {};

AG.NODE_TYPES = [
  { id: 'prompt',    label: 'Prompt',       sub: 'context',   inType: null,            outType: 'prompt',  icon: 'Pr', color: 'var(--type-prompt)' },
  { id: 'dataset',   label: 'Dataset',      sub: 'source',    inType: 'prompt',        outType: 'source',  icon: 'Ds', color: 'var(--type-source)' },
  { id: 'access',    label: 'Access Layer', sub: 'filter',    inType: 'source',        outType: 'files',   icon: 'Ac', color: 'var(--type-files)' },
  { id: 'index',     label: 'Index Layer',  sub: 'chunks',    inType: 'files',         outType: 'chunks',  icon: 'Ix', color: 'var(--type-chunks)' },
  { id: 'tags',      label: 'Tags',         sub: 'weight',    inType: 'chunks',        outType: 'tagged',  icon: 'Tg', color: 'var(--type-tags)' },
  { id: 'clusters',  label: 'Clusters',     sub: 'rank',      inType: 'tagged',        outType: 'ranked',  icon: 'Cl', color: 'var(--type-tags)' },
  { id: 'output',    label: 'Output',       sub: 'view',      inType: 'ranked',        outType: 'result',  icon: 'Ou', color: 'var(--type-result)' },
];

AG.TYPE_LABEL = {
  prompt: 'prompt:Context', source: 'source:Dataset', files: 'files:Filtered',
  chunks: 'chunks:Retrieved', tagged: 'chunks:Tagged', ranked: 'chunks:Ranked', result: 'result:LLM',
};

AG.CLUSTERS = [
  { id: 'theme',            label: 'Theme',           hint: 'What is this about?' },
  { id: 'object_entity',    label: 'Object / Entity', hint: 'Which things are mentioned?' },
  { id: 'event_process',    label: 'Event / Process', hint: 'What kind of occurrence?' },
  { id: 'time_relevance',   label: 'Time Relevance',  hint: 'When is this relevant?' },
  { id: 'information_need', label: 'Info Need',       hint: 'What evidence is supplied?' },
];

AG.DATASETS = [
  { id: 'source_alpha_demo', files: 12, chunks: 847, tags: 234 },
  { id: 'source_beta_demo',  files: 5,  chunks: 312, tags: 98 },
  { id: 'source_gamma_demo', files: 28, chunks: 2103, tags: 512 },
];

AG.SAMPLE_FILES = [
  { id: 'f_a001', path: 'records/batch_001.jsonl', fmt: 'jsonl', chunks: 45 },
  { id: 'f_a002', path: 'records/batch_002.jsonl', fmt: 'jsonl', chunks: 38 },
  { id: 'f_a003', path: 'reports/overview.pdf',    fmt: 'pdf',   chunks: 72 },
  { id: 'f_b001', path: 'tables/main.parquet',     fmt: 'parquet', chunks: 120 },
  { id: 'f_b002', path: 'meta/schema.yaml',        fmt: 'yaml',  chunks: 8 },
];

AG.SAMPLE_CHUNKS = [
  { id: 'c_a001_000', file: 'f_a001', preview: 'Revenue for Q2 showed a 12% increase year-over-year, driven primarily by expansion into new market segments.', rel: 0.92,
    tags: [
      { name: 'revenue_analysis', cluster: 'theme', w: 0.85 },
      { name: 'q2_2025', cluster: 'time_relevance', w: 0.91 },
      { name: 'quarterly_report', cluster: 'event_process', w: 0.72 },
    ]},
  { id: 'c_a001_001', file: 'f_a001', preview: 'The product launch in the Nordic region exceeded initial projections by 34%. Customer acquisition cost decreased to $47 per unit.', rel: 0.78,
    tags: [
      { name: 'market_expansion', cluster: 'theme', w: 0.78 },
      { name: 'product_launch', cluster: 'event_process', w: 0.65 },
      { name: 'acme_corp', cluster: 'object_entity', w: 0.92 },
    ]},
  { id: 'c_a001_002', file: 'f_a001', preview: 'Year-to-date performance against targets: revenue at 108%, retention at 94%, NPS improved from 42 to 51.', rel: 0.85,
    tags: [
      { name: 'performance_metric', cluster: 'theme', w: 0.88 },
      { name: 'comparison', cluster: 'information_need', w: 0.74 },
    ]},
  { id: 'c_a003_000', file: 'f_a003', preview: 'This annual overview consolidates findings from all twelve data batches processed during the evaluation period.', rel: 0.95,
    tags: [
      { name: 'annual_summary', cluster: 'theme', w: 0.93 },
      { name: 'historical', cluster: 'time_relevance', w: 0.70 },
    ]},
  { id: 'c_b001_000', file: 'f_b001', preview: '{"entity_id":"ENT-0042","type":"organisation","label":"Demo Systems Inc","sector":"technology","status":"active"}', rel: 0.60,
    tags: [
      { name: 'demo_systems_inc', cluster: 'object_entity', w: 0.95 },
      { name: 'active', cluster: 'time_relevance', w: 0.50 },
    ]},
];

// Per-stage payload samples: what to show in the edge drawer + per-node Inspector
AG.STAGE_PAYLOADS = {
  prompt: {
    inCount: null, outCount: 1,
    sample: [{ id: 'context', val: 'Q2 revenue trends — what changed and why?', w: '—' }],
  },
  dataset: {
    inCount: 1, outCount: 12,
    sample: [
      { id: 'source_alpha_demo', val: '12 files, 847 chunks, 234 tags', w: '—' },
    ],
  },
  access: {
    inCount: 12, outCount: 8,
    sample: AG.SAMPLE_FILES.slice(0,4).map(f => ({ id: f.id, val: f.path + '   ['+f.fmt+']', w: f.chunks })),
  },
  index: {
    inCount: 8, outCount: 312,
    sample: AG.SAMPLE_CHUNKS.slice(0,4).map(c => ({ id: c.id, val: c.preview, w: c.rel })),
  },
  tags: {
    inCount: 312, outCount: 312,
    sample: AG.SAMPLE_CHUNKS.slice(0,4).map(c => ({ id: c.id, val: c.tags.map(t => t.name).join(', '), w: c.tags.length })),
  },
  clusters: {
    inCount: 312, outCount: 47,
    sample: AG.SAMPLE_CHUNKS.slice(0,4).map((c, i) => ({ id: c.id, val: c.preview, w: (0.9 - i*0.07).toFixed(2) })),
  },
  output: {
    inCount: 47, outCount: 1,
    sample: [{ id: 'result', val: 'LLM response · 312 tokens out · 2840ms', w: '—' }],
  },
};

AG.PRESET_RESULTS = {
  // Lane A — full pipeline (tags + clusters ON)
  full: {
    response: 'Q2 revenue rose 12% year-over-year, driven by Nordic market expansion (product launch +34% vs projection) and operating margins improved 2.2pp. Year-to-date performance is at 108% of revenue target with retention at 94%. The annual overview confirms these trends sit within a broader pattern of operational efficiency gains.',
    chunks: 47, tokensIn: 1247, tokensOut: 312, durationMs: 2840,
    topClusters: ['theme', 'event_process', 'time_relevance'],
  },
  // Lane B — tags off (baseline)
  baseline: {
    response: 'The data mentions a 12% revenue increase in Q2 and a product launch in the Nordic region. However, one retrieved record appears to be an unrelated entity record for a technology company, suggesting the retrieval precision could be improved.',
    chunks: 312, tokensIn: 1189, tokensOut: 287, durationMs: 2610,
    topClusters: [],
  },
};
