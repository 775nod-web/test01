import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds static assets into ../backend/static so FastAPI can serve them
// directly in production. In dev, the Vite server proxies /api to the
// local FastAPI process so both can run with hot reload independently.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
