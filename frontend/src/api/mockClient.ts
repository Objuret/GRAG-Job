/**
 * mockClient.ts
 *
 * Mock implementation of the workbench API client.
 *
 * STRUCTURE
 * ─────────
 * Two sections:
 *   1. PIPELINE STAGES (existing) — used by canvas and catalog
 *   2. GRAPH QUERY METHODS (new) — used by the retrieval workbench
 *
 * TO SWAP IN A REAL BACKEND
 * ─────────────────────────
 * 1. Implement HttpApiClient with the same method signatures.
 * 2. Change the export at the bottom from MockApiClient to HttpApiClient.
 * 3. No component files should need to change.
 *
 * All components import only `mockApi`. Nothing imports from mockData.ts directly.
 */

import {
  mockStages, mockArtifacts, mockExecutions, mockAdapters,
  mockDatasets, mockFiles, mockChunks, mockFileTags, mockCanonicalTags,
  mockRetrievalResults,
} from '../data/mockData';
import type {
  Stage,
  Artifact,
  Execution,
  AdapterOption,
  BootstrapData,
  StartExecutionRequest,
  ComparisonResult,
  DatasetSource,
  GragFile,
  GragChunk,
  FileTagSummary,
  CanonicalTag,
  ClusterDimension,
  RetrievalConfig,
  RetrievalResult,
} from '../types';

// ─── Client ───────────────────────────────────────────────────────────────────

class MockApiClient {

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION 1: Pipeline stage methods (existing)
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * GET /api/bootstrap
   * Returns environment metadata displayed in the top strip.
   */
  async getBootstrap(): Promise<BootstrapData> {
    return delay({
      appName: 'GRAG Retrieval Workbench',
      version: '0.2.0',
      environment: 'local-mock',
    }, 150);
  }

  /**
   * GET /api/stages
   * Returns the full registered stage catalog.
   */
  async getStageCatalog(): Promise<Stage[]> {
    return delay([...mockStages], 250);
  }

  /**
   * GET /api/artifacts
   */
  async getArtifacts(): Promise<Artifact[]> {
    return delay([...mockArtifacts], 250);
  }

  /**
   * GET /api/artifacts?type=:artifactType
   */
  async getArtifactsByType(artifactType: string): Promise<Artifact[]> {
    return delay(
      mockArtifacts.filter(a => a.type === artifactType),
      200,
    );
  }

  /**
   * GET /api/artifacts/:id
   */
  async getArtifact(id: string): Promise<Artifact | null> {
    return delay(mockArtifacts.find(a => a.id === id) ?? null, 150);
  }

  /**
   * GET /api/adapters
   */
  async getAdapterOptions(): Promise<AdapterOption[]> {
    return delay([...mockAdapters], 200);
  }

  /**
   * GET /api/executions
   */
  async getExecutions(stageId?: string): Promise<Execution[]> {
    const result = stageId
      ? mockExecutions.filter(e => e.stageId === stageId)
      : [...mockExecutions];
    return delay(result, 250);
  }

  /**
   * GET /api/executions/:id
   */
  async getExecution(id: string): Promise<Execution | null> {
    return delay(mockExecutions.find(e => e.id === id) ?? null, 150);
  }

  /**
   * POST /api/executions
   */
  async startExecution(request: StartExecutionRequest): Promise<Execution> {
    const stage = mockStages.find(s => s.id === request.stageId);
    if (!stage) throw new Error(`Stage not found: ${request.stageId}`);
    if (stage.capabilityState !== 'runnable') {
      throw new Error(`Stage "${stage.label}" is not runnable (state: ${stage.capabilityState})`);
    }
    const id = `exec_mock_${Date.now()}`;
    const now = new Date().toISOString();
    return delay({
      id, stageId: stage.id, status: 'queued' as const,
      timestamps: { queued: now }, logs: [`[INFO]  Execution ${id} queued`],
      inputs: request.inputs, config: request.config, producedArtifactIds: [],
    }, 300);
  }

  /**
   * GET /api/artifacts/compare?left=:leftRef&right=:rightRef
   */
  async compareArtifacts(leftRef: string, rightRef: string): Promise<ComparisonResult> {
    return delay({
      leftRef, rightRef,
      metadataDiff: {}, countDiff: {}, schemaDiff: {},
      lineageDiff: {}, summaryDiff: {},
    }, 350);
  }

  /**
   * POST /api/executions/:id/cancel
   */
  async cancelExecution(_executionId: string): Promise<Execution | null> {
    return delay(null, 150);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SECTION 2: Graph query methods (retrieval workbench)
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * GET /api/datasets
   * Real: MATCH (s:Source) RETURN s.source_id, count of files, chunks, tags
   */
  async getDatasets(): Promise<DatasetSource[]> {
    return delay([...mockDatasets], 200);
  }

  /**
   * GET /api/datasets/:id/files
   * Real: MATCH (s:Source {source_id: $id})-[:CONTAINS]->(f:File) RETURN f
   */
  async getFiles(datasetId: string, formatFilter?: string): Promise<GragFile[]> {
    let files = mockFiles.filter(f => f.datasetId === datasetId);
    if (formatFilter && formatFilter !== 'All') {
      files = files.filter(f => f.formatFamily === formatFilter);
    }
    return delay(files, 200);
  }

  /**
   * GET /api/files/:fileId/chunks
   * Real: MATCH (f:File {file_id: $id})-[:HAS_CHUNK]->(c:Chunk) RETURN c + tags
   */
  async getChunks(fileId: string): Promise<GragChunk[]> {
    return delay(
      mockChunks.filter(c => c.fileId === fileId),
      200,
    );
  }

  /**
   * GET /api/files/:fileId/tags
   * Real: MATCH (f:File {file_id: $id})-[t:TAGGED]->(tag:Tag) RETURN tag, t
   */
  async getFileTags(_fileId: string, clusters?: ClusterDimension[]): Promise<FileTagSummary[]> {
    let tags = mockFileTags;
    if (clusters && clusters.length > 0) {
      tags = tags.filter(t => clusters.includes(t.cluster));
    }
    return delay(tags, 200);
  }

  /**
   * GET /api/canonical-tags
   * Real: MATCH (ct:CanonicalTag) RETURN ct
   */
  async getCanonicalTags(cluster?: ClusterDimension): Promise<CanonicalTag[]> {
    let tags = [...mockCanonicalTags];
    if (cluster) {
      tags = tags.filter(t => t.cluster === cluster);
    }
    return delay(tags, 200);
  }

  /**
   * POST /api/retrieval
   * The core retrieval endpoint.
   * Real: Queries graph → retrieves chunks → ranks by tag weights → sends to LLM → returns result.
   *
   * Mock: returns a pre-computed result, chosen by whether tags are enabled or not.
   * This simulates the difference between a graph-enhanced retrieval and a baseline.
   */
  async executeRetrieval(config: RetrievalConfig): Promise<RetrievalResult> {
    // Simulate: tags enabled → better result (mock #1), tags disabled → weaker result (mock #2)
    const mockResult = config.tagsEnabled
      ? { ...mockRetrievalResults[0] }
      : { ...mockRetrievalResults[1] };

    // Override config and give a fresh ID/timestamp
    return delay({
      ...mockResult,
      id: `ret_${Date.now()}`,
      config: { ...config },
      timestamp: new Date().toISOString(),
    }, 1500);
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function delay<T>(value: T, ms: number): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(value), ms));
}

// ─── Singleton Export ─────────────────────────────────────────────────────────
// All components import this. Swap MockApiClient → HttpApiClient here when ready.

export const mockApi = new MockApiClient();
