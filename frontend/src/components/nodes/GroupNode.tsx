import { memo } from 'react';
import { Handle, Position, type NodeProps, NodeResizer } from '@xyflow/react';

export const GroupNode = memo(({ data, selected }: NodeProps) => {
  return (
    <>
      <NodeResizer minWidth={200} minHeight={200} isVisible={selected} />
      <div className={`group-node ${selected ? 'selected' : ''}`}>
        <div className="group-node-label">
          {(data.label as string) || 'Pipeline Group'}
        </div>

        {/* Free-form connection handles */}
        <Handle type="target" position={Position.Top} id="top" />
        <Handle type="target" position={Position.Left} id="left" />
        <Handle type="source" position={Position.Bottom} id="bottom" />
        <Handle type="source" position={Position.Right} id="right" />
      </div>
    </>
  );
});

GroupNode.displayName = 'GroupNode';
