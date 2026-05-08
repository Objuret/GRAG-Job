// ─── Core Domain States ──────────────────────────────────────────────────────

export type StageCategory =
  | 'Dataset'
  | 'Access Layer'
  | 'Index Layer'
  | 'Tagging'
  | 'Clustering';

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

/** The five cluster dimensions used for tagging. */
export type ClusterDimension =
  | 'theme'
  | 'object_entity'
  | 'event_process'
  | 'time_relevance'
  | 'information_need';

export const ALL_CLUSTERS: ClusterDimension[] = [
  'theme', 'object_entity', 'event_process', 'time_relevance', 'information_need',
];

/** Cluster display metadata — labels and short descriptions. */
export const CLUSTER_META: Record<ClusterDimension, { label: string; hint: string }> = {
  theme:              { label: 'Theme',              hint: 'What is this about?' },
  object_entity:      { label: 'Object / Entity',    hint: 'Which things are mentioned?' },
  event_process:      { label: 'Event / Process',    hint: 'What kind of occurrence?' },
  time_relevance:     { label: 'Time Relevance',     hint: 'When is this relevant?' },
  information_need:   { label: 'Information Need',   hint: 'What evidence is supplied?' },
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
  cluster: ClusterDimension;
  weightLocal: number;
  canonicalId: string | null;
}

/** Aggregated (:File)-[:TAGGED]->(:Tag) edge. */
export interface FileTagSummary {
  tagName: string;
  cluster: ClusterDimension;
  weightGlobal: number;
  nChunks: number;
  canonicalId: string | null;
}

/** A :CanonicalTag node — the seeded vocabulary. */
export interface CanonicalTag {
  label: string;
  cluster: ClusterDimension;
  gloss: string;
}

/** Configuration for one retrieval pipeline line. */
export interface RetrievalConfig {
  datasetId: string;
  prompt: string;
  enabledClusters: ClusterDimension[];
  canonicalOnly: boolean;
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
    nodes: any[];       // ReactFlow node list — see WorkspaceContext for serialisation notes
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
