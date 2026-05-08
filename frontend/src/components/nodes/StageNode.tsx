import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Settings, Database, Share2, Layers, Search, Cpu, CheckCircle2, AlertCircle } from 'lucide-react';
import type { Stage } from '../../types';

export interface StageNodeData {
  stage: Stage;
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  'Dataset': <Database size={10} />,
  'Access Layer': <Layers size={10} />,
  'Index Layer': <Search size={10} />,
  'Tagging': <Share2 size={10} />,
  'Clustering': <Cpu size={10} />,
  'Output': <Cpu size={10} />,
};

export const StageNode = memo(({ data, selected }: NodeProps) => {
  const stage = data.stage as Stage;
  if (!stage) return null;

  const capClass = `cap-${stage.capabilityState}`;

  return (
    <div className={`stage-node ${capClass} ${selected ? 'selected' : ''}`}>
      {/* Input handles on top and left */}
      <Handle type="target" position={Position.Top} id="top" />
      <Handle type="target" position={Position.Left} id="left" />

      <div className="stage-node-content">
        <div className="stage-node-header">
          <div className="stage-node-title" title={stage.label}>{stage.label}</div>
          <div className="stage-node-cap">
            {stage.capabilityState === 'runnable' && <CheckCircle2 size={12} className="cap-icon-runnable" />}
            {stage.capabilityState === 'inspectable' && <Search size={12} className="cap-icon-inspectable" />}
            {stage.capabilityState === 'unavailable' && <AlertCircle size={12} className="cap-icon-unavailable" />}
            {stage.capabilityState === 'pending' && <Settings size={12} className="cap-icon-pending" />}
          </div>
        </div>

        <div className="stage-node-type">
          {CATEGORY_ICONS[stage.category] || <Settings size={10} />}
          <span style={{ marginLeft: 4 }}>{stage.type}</span>
        </div>

        <div className="stage-node-ports">
          <span className="stage-node-port">{stage.inputArtifactTypes.length > 0 ? stage.inputArtifactTypes.length + ' in' : '0 in'}</span>
          <span className={`stage-node-badge ${capClass}`}>{stage.capabilityState}</span>
          <span className="stage-node-port">{stage.outputArtifactTypes.length > 0 ? stage.outputArtifactTypes.length + ' out' : '0 out'}</span>
        </div>
      </div>

      {/* Output handles on bottom and right */}
      <Handle type="source" position={Position.Bottom} id="bottom" />
      <Handle type="source" position={Position.Right} id="right" />
    </div>
  );
});

StageNode.displayName = 'StageNode';
