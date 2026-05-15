// ─── Core Domain States ──────────────────────────────────────────────────────

export type StageCategory =
  | 'Dataset'
  | 'Access Layer'
  | 'Index Layer'
  | 'Tagging'
  | 'Facets';

export type CapabilityState = 'runnable' | 'inspectable' | 'unavailable' | 'pending';
export type ArtifactState   = 'valid' | 'invalid' | 'partial' | 'missing' | 'stale';
export type ExecutionState  = 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type Theme           = 'dark' | 'light' | 'pastel' | 'neo' | 'severance' | 'fallout';

// ─── Config Field Schema ──────────────────────────────────────────────────────
// Each field in Stage.configSchema is a ConfigFieldSchema object.
// Components render the appropriate input control based on `type`.

export type ConfigFieldType =
  | 'text'            // free text input
  | 'number'          // numeric input
  | 'textarea'        // multi-line text (e.g. prompt templates)
  | 'select'          // static option list — options[] is required
  | 'artifact-select' // dynamic: populated from getArtifactsByType(artifactType)
  | 'adapter-select'; // dynamic: populated from getAdapterOptions()

export interface ConfigFieldSchema {
  type: ConfigFieldType;
  label: string;
  required?: boolean;
  placeholder?: string;
  // Only for 'select':
  options?: string[];
  // Only for 'artifact-select':
  artifactType?: string;
}

// ─── Stage ───────────────────────────────────────────────────────────────────

export interface Stage {
  id: string;
  type: string;
  label: string;
  category: string;
  description: string;
  adapterKey: string;
  capabilityState: CapabilityState;
  inputArtifactTypes: string[];
  outputArtifactTypes: string[];
  configSchema: Record<string, ConfigFieldSchema>;
  panelDefinition: { type: 'form' | 'editor'; fields: string[] };
  lineageRules: Record<string, any>;
}

// ─── Artifact ─────────────────────────────────────────────────────────────────

export interface Artifact {
  id: string;
  type: string;
  label: string;
  state: ArtifactState;
  metadata: Record<string, any>;
  lineage: {
    sourceStageId?: string;
    parentArtifactIds: string[];
  };
  summary: Record<string, any>;
  preview?: {
    columns: string[];
    rows: any[][];
  };
}

// ─── Execution ────────────────────────────────────────────────────────────────

export interface Execution {
  id: string;
  stageId: string;
  status: ExecutionState;
  timestamps: {
    queued?: string;
    started?: string;
    completed?: string;
  };
  logs: string[];
  inputs: Record<string, string>;   // argName → artifactId
  config: Record<string, any>;
  producedArtifactIds: string[];
  error?: string;
}

// ─── Adapter ──────────────────────────────────────────────────────────────────

export type AdapterStatus = 'registered' | 'unregistered' | 'deprecated';

export interface AdapterOption {
  key: string;
  label: string;
  version: string;
  status: AdapterStatus;
}

// ─── API Payloads ─────────────────────────────────────────────────────────────

export interface BootstrapData {
  appName: string;
  version: string;
  environment: string;
}

export interface StartExecutionRequest {
  stageId: string;
  config: Record<string, any>;
  inputs: Record<string, string>; // argName → artifactId
}

export interface ComparisonResult {
  leftRef: string;
  rightRef: string;
  metadataDiff: Record<string, any>;
  countDiff: Record<string, any>;
  schemaDiff: Record<string, any>;
  lineageDiff: Record<string, any>;
  summaryDiff: Record<string, any>;
}

// ─── GRAG-Job Domain Types (Query Side) ──────────────────────────────────────
// These mirror the finished Neo4j graph built by GRAG-Job.
// The frontend queries this graph — it does not build it.

/** The five HERB facets used for tagging and retrieval. */
export type FacetDimension =
  | 'topic'
  | 'entities'
  | 'activity'
  | 'temporal'
  | 'evidence';

export const ALL_FACETS: FacetDimension[] = [
  'topic', 'entities', 'activity', 'temporal', 'evidence',
];

/** Facet display metadata - labels and short descriptions. */
export const FACET_META: Record<FacetDimension, { label: string; hint: string }> = {
  topic:     { label: 'Topic',    hint: 'What is this about?' },
  entities:  { label: 'Entities', hint: 'Which concrete things are named or referenced?' },
  activity:  { label: 'Activity', hint: 'What kind of event, process, or content action is described?' },
  temporal:  { label: 'Temporal', hint: 'When is this relevant: recent, historical, future, active, completed?' },
  evidence:  { label: 'Evidence', hint: 'What kind of answer material is supplied?' },
};

/** A :Source node — one per dataset in the graph. */
export interface DatasetSource {
  id: string;
  fileCount: number;
  chunkCount: number;
  tagCount: number;
}

/** A :File node — one per payload file. */
export interface GragFile {
  fileId: string;
  datasetId: string;
  relPath: string;
  formatFamily: string;
  description: string | null;
  chunkCount: number;
}

/** A :Chunk node — one per deterministic chunk. */
export interface GragChunk {
  chunkId: string;
  fileId: string;
  ordinal: number;
  kind: string;
  content: string;
  description: string | null;
  relevanceToFile: number | null;
  tags: ChunkTag[];
}

/** A (:Chunk)-[:HAS_TAG]->(:Tag) edge. */
export interface ChunkTag {
  tagName: string;
  facet: FacetDimension;
  wChunk: number;
  wFacet: number;
}

/** Optional file-level tag summary derived from (:Chunk)-[:HAS_TAG]->(:Tag). */
export interface FileTagSummary {
  tagName: string;
  facet: FacetDimension;
  wFacet: number;
  nChunks: number;
}

/** A :Tag node in the HERB graph. */
export interface GraphTag {
  name: string;
}

/** Configuration for one retrieval pipeline line. */
export interface RetrievalConfig {
  datasetId: string;
  prompt: string;
  enabledFacets: FacetDimension[];
  weightThreshold: number;
  maxChunks: number;
  formatFilter: string[];
  accessLayerEnabled: boolean;
  indexLayerEnabled: boolean;
  tagsEnabled: boolean;
}

/** Result from a retrieval run. */
export interface RetrievalResult {
  id: string;
  config: RetrievalConfig;
  retrievedChunks: GragChunk[];
  llmResponse: string;
  totalTokensIn: number;
  totalTokensOut: number;
  durationMs: number;
  timestamp: string;
}

// ─── Workspace Persistence ────────────────────────────────────────────────────

export interface WorkspaceState {
  schemaVersion: number;
  workspace: {
    nodes: any[];       // ReactFlow node list (optional future persistence)
    edges: any[];
    selectedNodeId: string | null;
    selectedArtifactId: string | null;
    selectedExecutionId: string | null;
    theme: Theme;
    configValues: Record<string, Record<string, any>>;  // stageId → fieldKey → value
    retrievalConfigs: Record<string, RetrievalConfig>;  // nodeId → config per pipeline line
    retrievalResults: Record<string, RetrievalResult>;  // nodeId → result per pipeline line
    prompt: string;                                      // shared prompt across all lines
  };
}
