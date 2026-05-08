import React from 'react';
import { Terminal, Columns } from 'lucide-react';
import { useWorkspace } from '../../store/WorkspaceContext';
import { CLUSTER_META } from '../../types';
import type { RetrievalResult } from '../../types';

export const ExecutionPanel: React.FC = () => {
  const { workspace } = useWorkspace();

  const results = Object.values(workspace.retrievalResults);

  if (results.length === 0) {
    return (
      <div className="execution-panel">
        <div className="execution-panel-header">
          <Terminal size={12} /> Retrieval Results
        </div>
        <div className="execution-panel-body">
          <div className="text-muted italic text-xs" style={{ padding: 10 }}>
            No retrieval runs yet. Configure the pipeline and click Execute.
          </div>
        </div>
      </div>
    );
  }

  // If 2+ results, show side-by-side comparison
  const showComparison = results.length >= 2;

  return (
    <div className="execution-panel">
      <div className="execution-panel-header">
        <Terminal size={12} /> Retrieval Results
        {showComparison && (
          <span className="badge state-runnable" style={{ marginLeft: 8 }}>
            <Columns size={10} /> Comparison
          </span>
        )}
      </div>
      <div className="execution-panel-body">
        {showComparison ? (
          <ComparisonView results={results.slice(-2)} />
        ) : (
          <SingleResultView result={results[results.length - 1]} />
        )}
      </div>
    </div>
  );
};

// ─── Single Result ────────────────────────────────────────────────────────────

const SingleResultView: React.FC<{ result: RetrievalResult }> = ({ result }) => {
  return (
    <div className="log-block">
      <div className="log-block-header">
        <span className="log-block-id">{result.id}</span>
        <span className="log-block-status state-succeeded">
          {result.retrievedChunks.length} chunks · {result.durationMs}ms
        </span>
      </div>
      <div className="log-block-body">
        <div className="text-xs text-muted" style={{ marginBottom: 4 }}>
          Tags: {result.config.tagsEnabled ? 'ON' : 'OFF'} ·
          Clusters: {result.config.enabledClusters.length > 0
            ? result.config.enabledClusters.map(c => CLUSTER_META[c].label).join(', ')
            : 'none'
          }
        </div>
        <div style={{ fontSize: 11, lineHeight: '1.5' }}>
          {result.llmResponse}
        </div>
      </div>
    </div>
  );
};

// ─── Side-by-Side Comparison ──────────────────────────────────────────────────

const ComparisonView: React.FC<{ results: RetrievalResult[] }> = ({ results }) => {
  const [a, b] = results;

  // Find chunks unique to each
  const aChunkIds = new Set(a.retrievedChunks.map(c => c.chunkId));
  const bChunkIds = new Set(b.retrievedChunks.map(c => c.chunkId));
  const onlyInA = a.retrievedChunks.filter(c => !bChunkIds.has(c.chunkId));
  const onlyInB = b.retrievedChunks.filter(c => !aChunkIds.has(c.chunkId));
  const shared = a.retrievedChunks.filter(c => bChunkIds.has(c.chunkId));

  return (
    <div className="comparison-grid">
      {/* Header row */}
      <div className="comparison-col">
        <div className="comparison-label">
          Line A: Tags {a.config.tagsEnabled ? 'ON' : 'OFF'}
        </div>
        <div className="comparison-stats">
          {a.retrievedChunks.length} chunks · {a.totalTokensIn}→{a.totalTokensOut} tokens · {a.durationMs}ms
        </div>
        <div className="comparison-response">
          {a.llmResponse}
        </div>
      </div>

      <div className="comparison-col">
        <div className="comparison-label">
          Line B: Tags {b.config.tagsEnabled ? 'ON' : 'OFF'}
        </div>
        <div className="comparison-stats">
          {b.retrievedChunks.length} chunks · {b.totalTokensIn}→{b.totalTokensOut} tokens · {b.durationMs}ms
        </div>
        <div className="comparison-response">
          {b.llmResponse}
        </div>
      </div>

      {/* Diff summary */}
      <div className="comparison-diff" style={{ gridColumn: '1 / -1' }}>
        <div className="text-xs" style={{ display: 'flex', gap: 16 }}>
          <span className="state-runnable">{shared.length} shared chunks</span>
          <span style={{ color: 'var(--accent-warm)' }}>{onlyInA.length} only in A</span>
          <span style={{ color: 'var(--accent-cool, #6ea8fe)' }}>{onlyInB.length} only in B</span>
        </div>
      </div>
    </div>
  );
};
