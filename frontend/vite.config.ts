import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Databricks Appsではバックエンド(FastAPI)がビルド成果物(dist)を配信する。
// 開発時は /api を Uvicorn(既定8000番)へプロキシし、相対パス呼び出しを再現する。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
