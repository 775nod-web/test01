import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Databricks Apps上ではバックエンド(FastAPI)が /api/* と静的ファイルの両方を
// 同一オリジンで配信するため、開発時のみ /api へのリクエストをバックエンドに
// プロキシする。バックエンドのポートは backend/main.py の起動設定に合わせる。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
