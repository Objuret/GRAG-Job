import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import type { Node as FlowNode, Edge as FlowEdge } from '@xyflow/react';
import type { RetrievalConfig, RetrievalResult } from '../types';

export interface WorkspaceState {
  nodes: FlowNode[];
  edges: FlowEdge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  selectedArtifactId: string | null;
  selectedExecutionId: string | null;
  activePanelTab: 'config' | 'inspect' | 'compare';
  configValues: Record<string, Record<string, any>>;
  // Retrieval workbench state
  retrievalConfigs: Record<string, RetrievalConfig>;  // nodeId → config per pipeline line
  retrievalResults: Record<string, RetrievalResult>;  // nodeId → result per output node
  prompt: string;                                      // shared prompt across all lines
}

const DEFAULT_STATE: WorkspaceState = {
  nodes: [],
  edges: [],
  selectedNodeId: null,
  selectedEdgeId: null,
  selectedArtifactId: null,
  selectedExecutionId: null,
  activePanelTab: 'config',
  configValues: {},
  retrievalConfigs: {},
  retrievalResults: {},
  prompt: '',
};

const STORAGE_KEY = 'artifact_pipeline_workspace';
const SCHEMA_VERSION = 2;

interface WorkspaceContextValue {
  workspace: WorkspaceState;
  updateWorkspace: (partial: Partial<WorkspaceState>) => void;
  clearWorkspace: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

// Strips React Flow internals (like measured, dragging, etc) to prevent stale state conflicts on reload.
function sanitizeNodeForStorage(n: FlowNode): FlowNode {
  const clean: any = {
    id: n.id,
    type: n.type,
    position: n.position,
    data: n.data
  };
  if (n.parentId) clean.parentId = n.parentId;
  if (n.extent) clean.extent = n.extent;
  if (n.style) clean.style = n.style;
  return clean as FlowNode;
}

/** Migrate schema v1 → v2: add retrieval workbench fields. */
function migrateWorkspace(stored: any): WorkspaceState {
  const ws = stored.workspace ?? {};
  if (stored.schemaVersion === 1) {
    return {
      ...DEFAULT_STATE,
      ...ws,
      retrievalConfigs: {},
      retrievalResults: {},
      prompt: '',
    };
  }
  return { ...DEFAULT_STATE, ...ws };
}

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [workspace, setWorkspace] = useState<WorkspaceState>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.schemaVersion && parsed.workspace) {
          if (parsed.schemaVersion < SCHEMA_VERSION) {
            return migrateWorkspace(parsed);
          }
          return { ...DEFAULT_STATE, ...parsed.workspace };
        }
      }
    } catch (e) {
      console.warn('Failed to parse workspace from localStorage', e);
    }
    return DEFAULT_STATE;
  });

  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveToStorage = useCallback((state: WorkspaceState) => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    
    // Debounce the save to prevent performance issues during dragging
    saveTimeoutRef.current = setTimeout(() => {
      const safeState = {
        ...state,
        nodes: state.nodes.map(sanitizeNodeForStorage)
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        schemaVersion: SCHEMA_VERSION,
        workspace: safeState
      }));
    }, 500);
  }, []);

  const updateWorkspace = useCallback((partial: Partial<WorkspaceState>) => {
    setWorkspace(prev => {
      const next = { ...prev, ...partial };
      saveToStorage(next);
      return next;
    });
  }, [saveToStorage]);

  const clearWorkspace = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setWorkspace(DEFAULT_STATE);
  }, []);

  return (
    <WorkspaceContext.Provider value={{ workspace, updateWorkspace, clearWorkspace }}>
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider');
  return ctx;
};
