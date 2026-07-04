import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ローカル開発時: `npm run dev` はViteの開発サーバー(通常5173)で起動し、
// /api/* へのリクエストはFastAPI(8000番)へプロキシする。
// 本番(Databricks Apps): `npm run build` でdist/を生成し、
// backend/main.py がその静的ファイルを配信する。
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
