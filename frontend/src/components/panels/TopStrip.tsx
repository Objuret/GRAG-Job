import React from 'react';
import { Database, Zap, RefreshCw } from 'lucide-react';
import { useWorkspace } from '../../store/WorkspaceContext';

export const TopStrip: React.FC = () => {
  const { clearWorkspace } = useWorkspace();
  
  return (
    <div className="top-strip">
      <div className="top-strip-left">
        <Database size={14} className="top-strip-icon" />
        <span className="top-strip-name">Artifact Pipeline Workbench</span>
        <span className="top-strip-env">local_dev</span>
      </div>
      <div className="top-strip-right">
        <span className="top-strip-version">v0.1.0</span>
        <ThemeSelector />
        <button 
          className="tool-btn" 
          style={{ padding: '3px 8px', width: 'auto' }} 
          title="Reset Workspace"
          onClick={() => {
            clearWorkspace();
            window.location.reload();
          }}
        >
          <RefreshCw size={12} />
        </button>
      </div>
    </div>
  );
};

const ThemeSelector: React.FC = () => {
  const themes = [
    { id: 'dark', label: 'Dark Synth' },
    { id: 'light', label: 'Commodore' },
    { id: 'pastel', label: 'Pastel' },
    { id: 'neo', label: 'Neo' },
    { id: 'severance', label: 'Severance' },
    { id: 'fallout', label: 'Fallout' }
  ];

  const handleThemeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    document.documentElement.setAttribute('data-theme', e.target.value);
  };

  return (
    <div className="theme-selector">
      <Zap size={10} className="theme-palette-icon" />
      <select className="theme-select-native" onChange={handleThemeChange} defaultValue="dark">
        {themes.map(t => (
          <option key={t.id} value={t.id}>{t.label}</option>
        ))}
      </select>
    </div>
  );
};
