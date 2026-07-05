import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Build output goes straight into ../app/static so the FastAPI backend
// (Phase 1) can serve the built SPA and the /api/* routes from one process
// on one origin — see docs/phase2_frontend.md for the hosting rationale.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../app/static'),
    emptyOutDir: true,
  },
  server: {
    // Dev-time only: proxy /api to the FastAPI dev server so the frontend
    // can always call relative "/api/..." paths, in dev and in prod alike.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
