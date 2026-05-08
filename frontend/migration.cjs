const fs = require('fs');

// 1. Copy styles
fs.copyFileSync('updated/styles.css', 'src/index.css');

// 2. Transform data.js -> src/data/mockData.ts
let dataContent = fs.readFileSync('updated/data.js', 'utf8');
// remove window.AG lines
dataContent = dataContent.replace(/window\.AG = window\.AG \|\| \{\};/, '');
// replace AG.X = ... with export const X = ...
dataContent = dataContent.replace(/AG\.([A-Z_]+) =/g, 'export const $1 =');
fs.writeFileSync('src/data/mockData.ts', dataContent);

// 3. Transform app.jsx -> src/App.jsx
let appContent = fs.readFileSync('updated/app.jsx', 'utf8');
appContent = appContent.replace(
  "const { NODE_TYPES, TYPE_LABEL, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS } = window.AG;",
  "import { NODE_TYPES, TYPE_LABEL, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS, SAMPLE_CHUNKS } from './data/mockData';\nimport { TopStrip, Catalog, Inspector, Drawer, BottomPanel, TweaksPanel } from './components/OldComponents'; // will inline or replace"
);

// wait, the app.jsx has everything in one file! So we don't need to import those components, they are defined inside app.jsx!
appContent = appContent.replace(
  "const { NODE_TYPES, TYPE_LABEL, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS } = window.AG;",
  "import { NODE_TYPES, TYPE_LABEL, CLUSTERS, DATASETS, STAGE_PAYLOADS, PRESET_RESULTS, SAMPLE_CHUNKS } from './data/mockData';"
);

// there are also references to window.AG.SAMPLE_CHUNKS in TagsPanel
appContent = appContent.replace(/window\.AG\.SAMPLE_CHUNKS/g, 'SAMPLE_CHUNKS');

// Finally, we need to export default App; at the bottom if it doesn't have it
if (!appContent.includes('export default App;')) {
  appContent += '\nexport default App;\n';
}

fs.writeFileSync('src/App.jsx', appContent);

// remove src/App.tsx
if (fs.existsSync('src/App.tsx')) {
  fs.unlinkSync('src/App.tsx');
}
