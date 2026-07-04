# Phase 2: フロントエンド（TypeScript + React）の構築

## 目的

Phase 1で作ったAPIを消費する、店長・本社営業管理・商品企画・データサイエンス
チーム向けのダッシュボードをTypeScript + Reactで実装する。**Streamlitは
使用しない。**

## やること

1. Viteで React + TypeScript プロジェクトを `serving_app/frontend` に作成する
   （`npm create vite@latest . -- --template react-ts` 相当の構成）。
2. `frontend/vite.config.ts` で開発時に `/api` を `http://localhost:8000`
   （FastAPI）へプロキシする設定を入れる。
3. `frontend/src/types.ts`: Gold layerの4表のレスポンス型を定義する。
   バックエンドのJSONキーは snake_case のままにしているので、TS側も
   snake_case のプロパティ名で合わせる（camelCase変換を挟むと
   バックエンドとの不一致に気づきにくいバグを生みやすい）。
4. `frontend/src/api.ts`: 4つのエンドポイントに対応するfetchラッパーを
   実装する。コンポーネント内で直接 `fetch` を書かない。
5. 以下のコンポーネントを実装する:
   - `StatTile`: KPI表示用の汎用タイル
   - `BarChart`: チャートライブラリに依存しない、プレーンなHTML/CSSの
     棒グラフ（`dataviz` skillの方針。直接ラベル＋凡例を必ず併記する）
   - `StoreRankingPanel` / `CategorySalesPanel`: 上記BarChartを使う
   - `DailyStoreSalesPanel`: 店舗フィルタ付きの明細表
   - `UnregisteredMasterReportPanel`: 課題種別をバッジ（アイコン＋ラベル）で
     表示する明細表
6. `App.tsx` で全体レイアウト（ヘッダー・KPI行・各パネル）を組み立てる。

## 完了確認

- `cd frontend && npm install && npm run build` が型エラーなく成功すること。
