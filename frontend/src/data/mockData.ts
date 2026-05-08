// Antigrav Workbench — mock data (synthetic only)
// Mirrors the structure in src/data/mockData.ts but tightened for the prototype.



import type {
  AdapterOption,
  Artifact,
  CanonicalTag,
  ClusterDimension,
  DatasetSource,
  Execution,
  FileTagSummary,
  GragChunk,
  GragFile,
  RetrievalConfig,
  RetrievalResult,
  Stage,
} from '../types';

export const NODE_TYPES = [
  { id: 'prompt',    label: 'Prompt',       sub: 'context',   inType: null,            outType: 'prompt',  icon: 'Pr', color: 'var(--type-prompt)' },
  { id: 'dataset',   label: 'Dataset',      sub: 'source',    inType: 'prompt',        outType: 'source',  icon: 'Ds', color: 'var(--type-source)' },
  { id: 'access',    label: 'Access Layer', sub: 'filter',    inType: 'source',        outType: 'files',   icon: 'Ac', color: 'var(--type-files)' },
  { id: 'index',     label: 'Index Layer',  sub: 'chunks',    inType: 'files',         outType: 'chunks',  icon: 'Ix', color: 'var(--type-chunks)' },
  { id: 'tags',      label: 'Tags',         sub: 'weight',    inType: 'chunks',        outType: 'tagged',  icon: 'Tg', color: 'var(--type-tags)' },
  { id: 'clusters',  label: 'Clusters',     sub: 'rank',      inType: 'tagged',        outType: 'ranked',  icon: 'Cl', color: 'var(--type-tags)' },
  { id: 'output',    label: 'Output',       sub: 'view',      inType: 'ranked',        outType: 'result',  icon: 'Ou', color: 'var(--type-result)' },
];

export const TYPE_LABEL = {
  prompt: 'prompt:Context', source: 'source:Dataset', files: 'files:Filtered',
  chunks: 'chunks:Retrieved', tagged: 'chunks:Tagged', ranked: 'chunks:Ranked', result: 'result:LLM',
};

export const CLUSTERS = [
  { id: 'theme',            label: 'Theme',           hint: 'What is this about?' },
  { id: 'object_entity',    label: 'Object / Entity', hint: 'Which things are mentioned?' },
  { id: 'event_process',    label: 'Event / Process', hint: 'What kind of occurrence?' },
  { id: 'time_relevance',   label: 'Time Relevance',  hint: 'When is this relevant?' },
  { id: 'information_need', label: 'Info Need',       hint: 'What evidence is supplied?' },
];

export const DATASETS = [
  { id: 'source_alpha_demo', files: 12, chunks: 847, tags: 234 },
  { id: 'source_beta_demo',  files: 5,  chunks: 312, tags: 98 },
  { id: 'source_gamma_demo', files: 28, chunks: 2103, tags: 512 },
];

export const SAMPLE_FILES = [
  { id: 'f_a001', path: 'records/batch_001.jsonl', fmt: 'jsonl', chunks: 45 },
  { id: 'f_a002', path: 'records/batch_002.jsonl', fmt: 'jsonl', chunks: 38 },
  { id: 'f_a003', path: 'reports/overview.pdf',    fmt: 'pdf',   chunks: 72 },
  { id: 'f_b001', path: 'tables/main.parquet',     fmt: 'parquet', chunks: 120 },
  { id: 'f_b002', path: 'meta/schema.yaml',        fmt: 'yaml',  chunks: 8 },
];

export const SAMPLE_CHUNKS = [
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
export const STAGE_PAYLOADS = {
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
    sample: SAMPLE_FILES.slice(0,4).map(f => ({ id: f.id, val: f.path + '   ['+f.fmt+']', w: f.chunks })),
  },
  index: {
    inCount: 8, outCount: 312,
    sample: SAMPLE_CHUNKS.slice(0,4).map(c => ({ id: c.id, val: c.preview, w: c.rel })),
  },
  tags: {
    inCount: 312, outCount: 312,
    sample: SAMPLE_CHUNKS.slice(0,4).map(c => ({ id: c.id, val: c.tags.map(t => t.name).join(', '), w: c.tags.length })),
  },
  clusters: {
    inCount: 312, outCount: 47,
    sample: SAMPLE_CHUNKS.slice(0,4).map((c, i) => ({ id: c.id, val: c.preview, w: (0.9 - i*0.07).toFixed(2) })),
  },
  output: {
    inCount: 47, outCount: 1,
    sample: [{ id: 'result', val: 'LLM response · 312 tokens out · 2840ms', w: '—' }],
  },
};

export const PRESET_RESULTS = {
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

const toCluster = (cluster: string): ClusterDimension => cluster as ClusterDimension;

export const mockStages: Stage[] = [
  {
    id: 'stage_dataset',
    type: 'dataset',
    label: 'Dataset',
    category: 'Source',
    description: 'Choose the synthetic source bundle for this workbench run.',
    adapterKey: 'dataset-source',
    capabilityState: 'runnable',
    inputArtifactTypes: [],
    outputArtifactTypes: ['source'],
    configSchema: {
      datasetId: { type: 'select', label: 'Dataset', options: DATASETS.map(d => d.id), required: true },
    },
    panelDefinition: { type: 'form', fields: ['datasetId'] },
    lineageRules: {},
  },
  {
    id: 'stage_accesslager',
    type: 'access',
    label: 'Access Layer',
    category: 'Retrieval',
    description: 'Filter files before chunk retrieval.',
    adapterKey: 'access-filter',
    capabilityState: 'runnable',
    inputArtifactTypes: ['source'],
    outputArtifactTypes: ['files'],
    configSchema: {
      enabled: { type: 'select', label: 'Enabled', options: ['On', 'Off'] },
      formatFilter: { type: 'select', label: 'Format', options: ['All', 'jsonl', 'pdf', 'parquet', 'yaml'] },
    },
    panelDefinition: { type: 'form', fields: ['enabled', 'formatFilter'] },
    lineageRules: {},
  },
  {
    id: 'stage_indexlager',
    type: 'index',
    label: 'Index Layer',
    category: 'Retrieval',
    description: 'Retrieve candidate chunks from the graph index.',
    adapterKey: 'chunk-index',
    capabilityState: 'runnable',
    inputArtifactTypes: ['files'],
    outputArtifactTypes: ['chunks'],
    configSchema: {
      enabled: { type: 'select', label: 'Enabled', options: ['On', 'Off'] },
      maxChunks: { type: 'number', label: 'Max chunks', placeholder: '50' },
    },
    panelDefinition: { type: 'form', fields: ['enabled', 'maxChunks'] },
    lineageRules: {},
  },
  {
    id: 'stage_tags',
    type: 'tags',
    label: 'Tags',
    category: 'Ranking',
    description: 'Rank chunks with the five graph tag dimensions.',
    adapterKey: 'tag-ranker',
    capabilityState: 'runnable',
    inputArtifactTypes: ['chunks'],
    outputArtifactTypes: ['tagged'],
    configSchema: {},
    panelDefinition: { type: 'form', fields: [] },
    lineageRules: {},
  },
  {
    id: 'stage_cluster',
    type: 'cluster',
    label: 'Output',
    category: 'Result',
    description: 'Inspect the generated answer and retrieved chunks.',
    adapterKey: 'output-view',
    capabilityState: 'inspectable',
    inputArtifactTypes: ['tagged'],
    outputArtifactTypes: ['result'],
    configSchema: {},
    panelDefinition: { type: 'form', fields: [] },
    lineageRules: {},
  },
];

export const mockAdapters: AdapterOption[] = [
  { key: 'dataset-source', label: 'Dataset Source', version: '0.1.0', status: 'registered' },
  { key: 'access-filter', label: 'Access Filter', version: '0.1.0', status: 'registered' },
  { key: 'chunk-index', label: 'Chunk Index', version: '0.1.0', status: 'registered' },
  { key: 'tag-ranker', label: 'Tag Ranker', version: '0.1.0', status: 'registered' },
];

export const mockDatasets: DatasetSource[] = DATASETS.map(dataset => ({
  id: dataset.id,
  fileCount: dataset.files,
  chunkCount: dataset.chunks,
  tagCount: dataset.tags,
}));

export const mockFiles: GragFile[] = SAMPLE_FILES.map(file => ({
  fileId: file.id,
  datasetId: 'source_alpha_demo',
  relPath: file.path,
  formatFamily: file.fmt,
  description: `${file.fmt.toUpperCase()} payload with ${file.chunks} synthetic chunks.`,
  chunkCount: file.chunks,
}));

export const mockChunks: GragChunk[] = SAMPLE_CHUNKS.map((chunk, ordinal) => ({
  chunkId: chunk.id,
  fileId: chunk.file,
  ordinal,
  kind: 'text',
  content: chunk.preview,
  description: chunk.preview,
  relevanceToFile: chunk.rel,
  tags: chunk.tags.map(tag => ({
    tagName: tag.name,
    cluster: toCluster(tag.cluster),
    weightLocal: tag.w,
    canonicalId: `canonical_${tag.name}`,
  })),
}));

export const mockFileTags: FileTagSummary[] = [
  { tagName: 'revenue_analysis', cluster: 'theme', weightGlobal: 0.85, nChunks: 2, canonicalId: 'canonical_revenue_analysis' },
  { tagName: 'market_expansion', cluster: 'theme', weightGlobal: 0.78, nChunks: 1, canonicalId: 'canonical_market_expansion' },
  { tagName: 'product_launch', cluster: 'event_process', weightGlobal: 0.65, nChunks: 1, canonicalId: 'canonical_product_launch' },
  { tagName: 'q2_2025', cluster: 'time_relevance', weightGlobal: 0.91, nChunks: 1, canonicalId: 'canonical_q2_2025' },
  { tagName: 'comparison', cluster: 'information_need', weightGlobal: 0.74, nChunks: 1, canonicalId: 'canonical_comparison' },
];

export const mockCanonicalTags: CanonicalTag[] = CLUSTERS.map(cluster => ({
  label: cluster.id,
  cluster: toCluster(cluster.id),
  gloss: cluster.hint,
}));

export const mockArtifacts: Artifact[] = [
  {
    id: 'artifact_source_alpha',
    type: 'source',
    label: 'Synthetic source alpha',
    state: 'valid',
    metadata: { files: 12, chunks: 847 },
    lineage: { parentArtifactIds: [] },
    summary: { datasetId: 'source_alpha_demo' },
  },
  {
    id: 'artifact_chunks_alpha',
    type: 'chunks',
    label: 'Retrieved synthetic chunks',
    state: 'valid',
    metadata: { chunks: SAMPLE_CHUNKS.length },
    lineage: { sourceStageId: 'stage_indexlager', parentArtifactIds: ['artifact_source_alpha'] },
    summary: { topFile: 'records/batch_001.jsonl' },
  },
];

export const mockExecutions: Execution[] = [
  {
    id: 'exec_demo_001',
    stageId: 'stage_indexlager',
    status: 'succeeded',
    timestamps: {
      queued: '2026-05-07T12:00:00.000Z',
      started: '2026-05-07T12:00:02.000Z',
      completed: '2026-05-07T12:00:05.000Z',
    },
    logs: ['Queued synthetic retrieval.', 'Retrieved candidate chunks.', 'Completed.'],
    inputs: { source: 'artifact_source_alpha' },
    config: { maxChunks: 50 },
    producedArtifactIds: ['artifact_chunks_alpha'],
  },
];

const makeRetrievalConfig = (tagsEnabled: boolean): RetrievalConfig => ({
  datasetId: 'source_alpha_demo',
  prompt: 'Q2 revenue trends - what changed and why?',
  enabledClusters: ['theme', 'event_process', 'time_relevance'],
  canonicalOnly: false,
  weightThreshold: 0,
  maxChunks: 50,
  formatFilter: [],
  accessLayerEnabled: true,
  indexLayerEnabled: true,
  tagsEnabled,
});

export const mockRetrievalResults: RetrievalResult[] = [
  {
    id: 'ret_full_demo',
    config: makeRetrievalConfig(true),
    retrievedChunks: mockChunks.slice(0, 4),
    llmResponse: PRESET_RESULTS.full.response,
    totalTokensIn: PRESET_RESULTS.full.tokensIn,
    totalTokensOut: PRESET_RESULTS.full.tokensOut,
    durationMs: PRESET_RESULTS.full.durationMs,
    timestamp: '2026-05-07T12:01:00.000Z',
  },
  {
    id: 'ret_baseline_demo',
    config: makeRetrievalConfig(false),
    retrievedChunks: mockChunks,
    llmResponse: PRESET_RESULTS.baseline.response,
    totalTokensIn: PRESET_RESULTS.baseline.tokensIn,
    totalTokensOut: PRESET_RESULTS.baseline.tokensOut,
    durationMs: PRESET_RESULTS.baseline.durationMs,
    timestamp: '2026-05-07T12:02:00.000Z',
  },
];
