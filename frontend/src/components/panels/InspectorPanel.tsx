import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { Settings, Activity, Play, Tag, Database, Search, Cpu, ToggleLeft, ToggleRight } from 'lucide-react';
import { useWorkspace } from '../../store/WorkspaceContext';
import { mockApi } from '../../api/mockClient';
import type { Stage, DatasetSource, ClusterDimension, RetrievalConfig } from '../../types';
import { ALL_CLUSTERS as CLUSTERS, CLUSTER_META as META } from '../../types';

export const InspectorPanel: React.FC = () => {
  const { workspace } = useWorkspace();
  
  const stage = useMemo<Stage | null>(() => {
    if (!workspace.selectedNodeId) return null;
    const node = workspace.nodes.find(n => n.id === workspace.selectedNodeId);
    return (node?.data?.stage as Stage) ?? null;
  }, [workspace.selectedNodeId, workspace.nodes]);

  if (!stage) {
    return (
      <div className="inspector-panel empty-state">
        Select a node to inspect its properties.
      </div>
    );
  }

  return (
    <div className="inspector-panel">
      <div className="panel-title">
        <Settings size={12} /> Stage Inspector
      </div>
      
      {/* Stage info card */}
      <div className="detail-card">
        <div className="detail-card-header">
          <span className="font-semibold text-main">{stage.label}</span>
          <span className={`badge state-${stage.capabilityState}`}>{stage.capabilityState}</span>
        </div>
        <div className="text-xs text-muted mb-2">{stage.description}</div>
        <div className="text-xs">
          Type: <span className="code">{stage.type}</span>
        </div>
      </div>

      {/* Shared prompt (shown for all nodes) */}
      <PromptSection />

      {/* Stage-specific config */}
      {stage.type === 'dataset' && <DatasetConfig />}
      {stage.type === 'tags' && <TagsConfig />}
      {stage.type === 'cluster' && <OutputView />}

      {/* Generic config form for other stages */}
      {stage.type !== 'dataset' && stage.type !== 'tags' && stage.type !== 'cluster' && (
        <GenericConfig stage={stage} />
      )}

      {/* Run button */}
      <div className="panel-title mt-2">
        <Activity size={12} /> Actions
      </div>
      <RunButton />
    </div>
  );
};

// ─── Prompt Section ────────────────────────────────────────────────────────────

const PromptSection: React.FC = () => {
  const { workspace, updateWorkspace } = useWorkspace();

  return (
    <div className="detail-card mt-2">
      <div className="panel-title" style={{ marginBottom: 6 }}>
        <Search size={12} /> Query Prompt
      </div>
      <textarea
        className="field-input"
        style={{ minHeight: 60, resize: 'vertical', fontFamily: 'inherit' }}
        placeholder="Enter your retrieval query..."
        value={workspace.prompt}
        onChange={e => updateWorkspace({ prompt: e.target.value })}
      />
      <div className="field-hint">Shared across all pipeline lines.</div>
    </div>
  );
};

// ─── Dataset Config ────────────────────────────────────────────────────────────

const DatasetConfig: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetSource[]>([]);
  const { workspace, updateWorkspace } = useWorkspace();

  useEffect(() => {
    mockApi.getDatasets().then(setDatasets);
  }, []);

  const selectedId = workspace.configValues?.['stage_dataset']?.datasetId ?? '';

  const handleChange = (datasetId: string) => {
    updateWorkspace({
      configValues: {
        ...workspace.configValues,
        stage_dataset: { datasetId },
      },
    });
  };

  const selectedDataset = datasets.find(d => d.id === selectedId);

  return (
    <div className="detail-card mt-2">
      <div className="panel-title" style={{ marginBottom: 6 }}>
        <Database size={12} /> Dataset Selection
      </div>
      <div className="select-wrap">
        <select
          className="field-select"
          value={selectedId}
          onChange={e => handleChange(e.target.value)}
        >
          <option value="">— Select dataset —</option>
          {datasets.map(d => (
            <option key={d.id} value={d.id}>{d.id}</option>
          ))}
        </select>
      </div>
      {selectedDataset && (
        <div className="text-xs mt-1" style={{ display: 'flex', gap: 12 }}>
          <span>{selectedDataset.fileCount} files</span>
          <span>{selectedDataset.chunkCount} chunks</span>
          <span>{selectedDataset.tagCount} tags</span>
        </div>
      )}
    </div>
  );
};

// ─── Tags Config (5 cluster toggles) ──────────────────────────────────────────

const TagsConfig: React.FC = () => {
  const { workspace, updateWorkspace } = useWorkspace();

  const tagConfig = workspace.configValues?.['stage_tags'] ?? {
    enabled: 'On',
    clusters: CLUSTERS as string[],
    canonicalOnly: 'No',
    weightThreshold: 0,
  };

  const enabledClusters: ClusterDimension[] = Array.isArray(tagConfig.clusters)
    ? tagConfig.clusters
    : CLUSTERS;

  const updateTagConfig = (patch: Record<string, any>) => {
    updateWorkspace({
      configValues: {
        ...workspace.configValues,
        stage_tags: { ...tagConfig, ...patch },
      },
    });
  };

  const toggleCluster = (cluster: ClusterDimension) => {
    const next = enabledClusters.includes(cluster)
      ? enabledClusters.filter(c => c !== cluster)
      : [...enabledClusters, cluster];
    updateTagConfig({ clusters: next });
  };

  return (
    <div className="detail-card mt-2">
      <div className="panel-title" style={{ marginBottom: 6 }}>
        <Tag size={12} /> Cluster Dimensions
      </div>

      {/* Module toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <button
          className="tool-btn"
          style={{ padding: '3px 10px', width: 'auto' }}
          onClick={() => updateTagConfig({ enabled: tagConfig.enabled === 'On' ? 'Off' : 'On' })}
        >
          {tagConfig.enabled === 'On'
            ? <><ToggleRight size={14} /> Enabled</>
            : <><ToggleLeft size={14} /> Disabled</>
          }
        </button>
        <span className="text-xs text-muted">
          {tagConfig.enabled === 'Off' ? 'Baseline mode — no tag ranking' : ''}
        </span>
      </div>

      {/* Cluster toggles */}
      {tagConfig.enabled === 'On' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {CLUSTERS.map(cluster => {
            const meta = META[cluster];
            const isOn = enabledClusters.includes(cluster);
            return (
              <button
                key={cluster}
                className={`cluster-toggle ${isOn ? 'cluster-on' : 'cluster-off'}`}
                onClick={() => toggleCluster(cluster)}
                title={meta.hint}
              >
                <span className="cluster-toggle-label">{meta.label}</span>
                <span className="cluster-toggle-hint">{meta.hint}</span>
                <span className={`cluster-toggle-state ${isOn ? 'state-runnable' : 'state-unavailable'}`}>
                  {isOn ? 'ON' : 'OFF'}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Canonical-only toggle */}
      {tagConfig.enabled === 'On' && (
        <div style={{ marginTop: 10 }}>
          <label className="field-label">Canonical Tags Only</label>
          <div className="select-wrap">
            <select
              className="field-select"
              value={tagConfig.canonicalOnly ?? 'No'}
              onChange={e => updateTagConfig({ canonicalOnly: e.target.value })}
            >
              <option value="No">No — include proposals</option>
              <option value="Yes">Yes — canonical only</option>
            </select>
          </div>
        </div>
      )}

      {/* Weight threshold */}
      {tagConfig.enabled === 'On' && (
        <div style={{ marginTop: 10 }}>
          <label className="field-label">Weight Threshold</label>
          <input
            type="number"
            className="field-input"
            step="0.1"
            min="0"
            max="1"
            value={tagConfig.weightThreshold ?? 0}
            onChange={e => updateTagConfig({ weightThreshold: parseFloat(e.target.value) || 0 })}
          />
          <div className="field-hint">Tags below this weight_global are excluded.</div>
        </div>
      )}
    </div>
  );
};

// ─── Output View ──────────────────────────────────────────────────────────────

const OutputView: React.FC = () => {
  const { workspace } = useWorkspace();

  // Find the result for the selected output node (or the first available)
  const result = workspace.selectedNodeId
    ? workspace.retrievalResults[workspace.selectedNodeId]
    : undefined;

  if (!result) {
    return (
      <div className="detail-card mt-2">
        <div className="panel-title" style={{ marginBottom: 6 }}>
          <Cpu size={12} /> Output
        </div>
        <div className="text-xs text-muted italic">
          No retrieval result yet. Configure the pipeline and click Execute.
        </div>
      </div>
    );
  }

  return (
    <div className="detail-card mt-2">
      <div className="panel-title" style={{ marginBottom: 6 }}>
        <Cpu size={12} /> Retrieval Result
      </div>

      {/* LLM Response */}
      <div style={{ marginBottom: 10 }}>
        <label className="field-label">LLM Response</label>
        <div className="code-block" style={{ whiteSpace: 'pre-wrap', fontSize: 11, lineHeight: '1.5' }}>
          {result.llmResponse}
        </div>
      </div>

      {/* Stats */}
      <div className="text-xs" style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
        <span>{result.retrievedChunks.length} chunks retrieved</span>
        <span>{result.totalTokensIn} in / {result.totalTokensOut} out</span>
        <span>{result.durationMs}ms</span>
      </div>

      {/* Retrieved chunks */}
      <label className="field-label">Retrieved Chunks ({result.retrievedChunks.length})</label>
      <div style={{ maxHeight: 200, overflowY: 'auto' }}>
        {result.retrievedChunks.map(chunk => (
          <div key={chunk.chunkId} className="chunk-card">
            <div className="chunk-card-header">
              <span className="code">{chunk.chunkId}</span>
              <span className="text-xs text-muted">relevance: {chunk.relevanceToFile?.toFixed(2) ?? '—'}</span>
            </div>
            <div className="text-xs" style={{ marginTop: 4 }}>{chunk.description}</div>
            <div className="chunk-tags">
              {chunk.tags.map((t, i) => (
                <span key={i} className={`tag-badge cluster-${t.cluster}`}>
                  {t.tagName} ({t.weightLocal.toFixed(2)})
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── Generic Config Form ──────────────────────────────────────────────────────

const GenericConfig: React.FC<{ stage: Stage }> = ({ stage }) => {
  const { workspace, updateWorkspace } = useWorkspace();
  const stageConfig = workspace.configValues?.[stage.id] ?? {};

  const handleChange = (key: string, value: any) => {
    updateWorkspace({
      configValues: {
        ...workspace.configValues,
        [stage.id]: { ...stageConfig, [key]: value },
      },
    });
  };

  return (
    <div className="detail-card mt-2">
      <div className="panel-title" style={{ marginBottom: 6 }}>
        <Settings size={12} /> Configuration
      </div>
      {Object.entries(stage.configSchema).map(([key, field]: [string, any]) => (
        <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
          <label className="field-label">
            {field.label} {field.required && <span className="field-required">*</span>}
          </label>
          {field.type === 'select' ? (
            <div className="select-wrap">
              <select
                className="field-select"
                value={stageConfig[key] ?? ''}
                onChange={e => handleChange(key, e.target.value)}
              >
                {field.options?.map((opt: string) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          ) : field.type === 'number' ? (
            <input
              type="number"
              className="field-input"
              placeholder={field.placeholder}
              value={stageConfig[key] ?? ''}
              onChange={e => handleChange(key, e.target.value)}
            />
          ) : (
            <input
              type="text"
              className="field-input"
              placeholder={field.placeholder}
              value={stageConfig[key] ?? ''}
              onChange={e => handleChange(key, e.target.value)}
            />
          )}
          {field.description && <div className="field-hint">{field.description}</div>}
        </div>
      ))}
      {Object.keys(stage.configSchema).length === 0 && (
        <div className="text-xs text-muted italic">No configuration required.</div>
      )}
    </div>
  );
};

// ─── Run Button ───────────────────────────────────────────────────────────────

const RunButton: React.FC = () => {
  const { workspace, updateWorkspace } = useWorkspace();
  const [running, setRunning] = useState(false);

  const handleRun = useCallback(async () => {
    if (running) return;
    setRunning(true);

    try {
      const datasetId = workspace.configValues?.['stage_dataset']?.datasetId ?? '';
      const tagConfig = workspace.configValues?.['stage_tags'] ?? {};

      const config: RetrievalConfig = {
        datasetId,
        prompt: workspace.prompt,
        enabledClusters: Array.isArray(tagConfig.clusters) ? tagConfig.clusters : CLUSTERS,
        canonicalOnly: tagConfig.canonicalOnly === 'Yes',
        weightThreshold: parseFloat(tagConfig.weightThreshold) || 0,
        maxChunks: parseInt(workspace.configValues?.['stage_indexlager']?.maxChunks) || 50,
        formatFilter: workspace.configValues?.['stage_accesslager']?.formatFilter ? [workspace.configValues['stage_accesslager'].formatFilter] : [],
        accessLayerEnabled: workspace.configValues?.['stage_accesslager']?.enabled !== 'Off',
        indexLayerEnabled: workspace.configValues?.['stage_indexlager']?.enabled !== 'Off',
        tagsEnabled: tagConfig.enabled !== 'Off',
      };

      const result = await mockApi.executeRetrieval(config);

      // Store result on the Output node (find the cluster/output stage node)
      const outputNode = workspace.nodes.find(n => (n.data?.stage as Stage)?.type === 'cluster');
      if (outputNode) {
        updateWorkspace({
          retrievalResults: {
            ...workspace.retrievalResults,
            [outputNode.id]: result,
          },
        });
      }
    } finally {
      setRunning(false);
    }
  }, [workspace, updateWorkspace, running]);

  return (
    <button
      className={`run-btn ${running ? 'disabled' : ''}`}
      disabled={running}
      onClick={handleRun}
    >
      <Play size={14} /> {running ? 'Running...' : 'Execute Retrieval'}
    </button>
  );
};
