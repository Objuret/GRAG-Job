import React, { useCallback, useEffect, useRef } from 'react';
import { 
  ReactFlow, 
  useNodesState, 
  useEdgesState, 
  useReactFlow, 
  type Connection, 
  type Edge,
  addEdge,
  ConnectionMode,
  type NodeChange,
  Background,
  Controls
} from '@xyflow/react';
import { useWorkspace } from '../../store/WorkspaceContext';
import { mockApi } from '../../api/mockClient';
import { StageNode } from '../nodes/StageNode';
import { GroupNode } from '../nodes/GroupNode';
import { TopStrip } from '../panels/TopStrip';
import { NodeCatalog } from '../panels/NodeCatalog';
import { InspectorPanel } from '../panels/InspectorPanel';
import { ExecutionPanel } from '../panels/ExecutionPanel';

const nodeTypes = {
  stageNode: StageNode,
  groupNode: GroupNode
};

export const Workbench: React.FC = () => {
  const { workspace, updateWorkspace } = useWorkspace();
  const { screenToFlowPosition } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState(workspace.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(workspace.edges);

  const didPopulate = useRef(false);

  // On first load with empty canvas: create a full pipeline line
  useEffect(() => {
    if (didPopulate.current || nodes.length > 0) return;
    didPopulate.current = true;

    mockApi.getStageCatalog().then(catalog => {
      // Build a complete pipeline: Dataset → Access → Index → Tags → Output
      const stageOrder = ['stage_dataset', 'stage_accesslager', 'stage_indexlager', 'stage_tags', 'stage_cluster'];
      const xStart = 80;
      const xGap = 280;
      const y = 120;

      const initialNodes = stageOrder
        .map((stageId, i) => {
          const stage = catalog.find(s => s.id === stageId);
          if (!stage) return null;
          return {
            id: `${stageId}_1`,
            type: 'stageNode',
            position: { x: xStart + i * xGap, y },
            data: { stage },
          };
        })
        .filter(Boolean) as any[];

      // Connect them in sequence: Dataset → Access → Index → Tags → Output
      const initialEdges: Edge[] = [];
      for (let i = 0; i < initialNodes.length - 1; i++) {
        initialEdges.push({
          id: `e_${initialNodes[i].id}_${initialNodes[i + 1].id}`,
          source: initialNodes[i].id,
          target: initialNodes[i + 1].id,
          sourceHandle: 'right',
          targetHandle: 'left',
          type: 'smoothstep',
          animated: true,
        });
      }

      setNodes(initialNodes);
      setEdges(initialEdges);
      updateWorkspace({ nodes: initialNodes, edges: initialEdges });
    });
  }, [nodes.length, setEdges, setNodes, updateWorkspace]);

  const handleNodesChange = useCallback((changes: NodeChange[]) => {
    onNodesChange(changes);
    // Persist position and structure, but ignore pure dimension changes to avoid loops
    if (changes.some(c => c.type === 'position' || c.type === 'remove' || c.type === 'add')) {
      // A small hack: we use a timeout so the ReactFlow state has time to update internally
      setTimeout(() => {
        setNodes(curr => {
          updateWorkspace({ nodes: curr });
          return curr;
        });
      }, 0);
    }
  }, [onNodesChange, updateWorkspace, setNodes]);

  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => {
      const next = addEdge({ ...connection, type: 'smoothstep', animated: true }, eds);
      updateWorkspace({ edges: next });
      return next;
    });
  }, [setEdges, updateWorkspace]);

  const isValidConnection = useCallback((conn: Edge | Connection) => {
    return conn.source !== conn.target;
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow');
      if (!type) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // Simple centering
      position.x -= 100;
      position.y -= 40;

      const newNode: any = {
        id: `${type}_${Date.now()}`,
        type,
        position,
        data: {}
      };

      if (type === 'stageNode') {
        const stageId = event.dataTransfer.getData('stageId');
        mockApi.getStageCatalog().then(catalog => {
          const stage = catalog.find(s => s.id === stageId);
          if (stage) {
            newNode.data = { stage };
            setNodes((nds) => {
              const next = nds.concat(newNode);
              updateWorkspace({ nodes: next });
              return next;
            });
          }
        });
      } else {
        newNode.data = { label: 'New Group' };
        newNode.style = { width: 300, height: 300 };
        setNodes((nds) => {
          const next = nds.concat(newNode);
          updateWorkspace({ nodes: next });
          return next;
        });
      }
    },
    [screenToFlowPosition, setNodes, updateWorkspace]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onSelectionChange = useCallback(({ nodes: selectedNodes, edges: selectedEdges }: any) => {
    updateWorkspace({
      selectedNodeId: selectedNodes.length === 1 ? selectedNodes[0].id : null,
      selectedEdgeId: selectedEdges.length === 1 ? selectedEdges[0].id : null
    });
  }, [updateWorkspace]);

  return (
    <div className="workbench-layout">
      <TopStrip />
      
      <div className="workbench-main">
        <div className="left-panel-container">
          <NodeCatalog />
        </div>

        <div className="workbench-canvas-container">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            nodeTypes={nodeTypes}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onSelectionChange={onSelectionChange}
            connectionMode={ConnectionMode.Loose}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>

        <div className="right-panel-container">
          <InspectorPanel />
        </div>
      </div>

      <div className="bottom-panel-container">
        <ExecutionPanel />
      </div>
    </div>
  );
};
