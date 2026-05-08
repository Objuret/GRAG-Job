import React, { useEffect, useState } from 'react';
import { Layers, Search, Box } from 'lucide-react';
import { mockApi } from '../../api/mockClient';
import type { Stage } from '../../types';

export const NodeCatalog: React.FC = () => {
  const [stages, setStages] = useState<Stage[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    mockApi.getStageCatalog().then(setStages);
  }, []);

  const onDragStart = (event: React.DragEvent, nodeType: string, label?: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    if (label) event.dataTransfer.setData('label', label);
    event.dataTransfer.effectAllowed = 'move';
  };

  const categories = Array.from(new Set(stages.map(s => s.category)));
  const filteredStages = stages.filter(s => 
    s.label.toLowerCase().includes(searchQuery.toLowerCase()) || 
    s.type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="catalog">
      <div style={{ display: 'flex', gap: 8 }}>
        <button 
          className="tool-btn" 
          draggable 
          onDragStart={(e) => onDragStart(e, 'groupNode')}
        >
          <Box size={14} /> Group
        </button>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="catalog-section-title"><Layers size={11} /> Pipeline Stages</div>
        
        <div style={{ padding: '0 0 10px 0' }}>
          <div style={{ position: 'relative' }}>
            <Search size={12} style={{ position: 'absolute', left: 8, top: 7, color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search stages..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="field-input"
              style={{ paddingLeft: 24 }}
            />
          </div>
        </div>
        
        <div style={{ flex: 1 }}>
          {categories.map(cat => {
            const catStages = filteredStages.filter(s => s.category === cat);
            if (catStages.length === 0) return null;
            return (
              <div key={cat} style={{ marginBottom: 14 }}>
                <div className="category-label">{cat}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {catStages.map(stage => (
                    <div
                      key={stage.id}
                      className={`catalog-item state-${stage.capabilityState}`}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData('application/reactflow', 'stageNode');
                        e.dataTransfer.setData('stageId', stage.id);
                        e.dataTransfer.effectAllowed = 'move';
                      }}
                      title={stage.description}
                    >
                      <div className="catalog-item-name">{stage.label}</div>
                      <div className="catalog-item-meta">
                        <span className="catalog-item-type">{stage.type}</span>
                        <span className={`badge state-${stage.capabilityState}`}>
                          {stage.capabilityState}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
