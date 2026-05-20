import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { ragasExportsFs } from './vite-plugins/ragasExportsFs'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), ragasExportsFs(repoRoot)],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
})
