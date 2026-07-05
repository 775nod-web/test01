# Phase 2: フロントエンド（TypeScript + React）実装 — 結果報告

実施日: 2026-07-05

## 実装したもの

`retail_sales_demo/frontend/` に Vite + React + TypeScript でSPAを実装した（Streamlit不使用）。

```
frontend/
  vite.config.ts        # build.outDir を ../app/static に固定。devサーバーは /api を :8000 にプロキシ
  src/
    theme.css            # デザイントークン（CLAUDE.mdと同期）
    types.ts             # backend/main.py のレスポンスモデルと対応するTS型
    api/client.ts        # 5エンドポイントのfetchラッパー（相対パス "/api/..."）
    format.ts            # 通貨/数値フォーマット、前期間比較の計算
    hooks/
      useAsync.ts         # 汎用データ取得フック
      useStoreOptions.ts  # store-ranking から店舗一覧を導出（専用エンドポイント未整備のため）
      useIssueTypeOptions.ts
    components/
      RoleSwitcher.tsx    # 表示ロール切替セレクタ
      KpiCard.tsx         # KPIカード（淡色背景＋濃色テキスト、増減でGreen/Coral）
      FilterBar.tsx       # 店舗（複数選択）/期間/前期間比較トグル
      Phase3Placeholder.tsx  # Phase3未実装機能の枠（アラート/quarantine率推移）
      RequeueButton.tsx   # 「再照合を実行」ダミーボタン
      charts/
        DailyStoreSalesChart.tsx  # Recharts LineChart
        CategorySalesChart.tsx    # Recharts BarChart
    views/
      HqDashboardView.tsx        # 本社経営ダッシュボード
      StoreView.tsx              # 店舗ビュー
      ProductPlanningView.tsx    # 商品企画ビュー
      DataQualityView.tsx        # データ品質ビュー
    App.tsx               # ロール切替 + 選択ビューの描画
```

## デザイントークン

`CLAUDE.md`（Phase 2で新規追記）に定義した Pastel Blue/Green/Coral/Yellow/Purple と Off White背景を
`src/theme.css` のCSS変数として実装し、全画面・全コンポーネントから参照している。KPIカードは淡色背景＋
濃色テキストを基本とし、`KpiCard` は前期間比の符号に応じて背景を `--pastel-green`（増加）/
`--pastel-coral`（減少）に切り替える（`deltaPct` が渡されない場合は中立の `--pastel-blue`）。

## 4画面の実装内容

1. **本社経営ダッシュボード**（`HqDashboardView`）: KPIカード5枚（net sales / gross sales(暫定) /
   transaction count / units sold / average basket size）、日別×店舗売上推移チャート、
   売上急減アラート（`Phase3Placeholder` で枠のみ）。期間を両方指定すると「前期間と比較」トグルが
   有効になり、同じ日数分遡った期間のKPIを取得して前期間比%をKPIカードに表示する。
2. **店舗ビュー**（`StoreView`）: 上部の「ログインシミュレーション」セレクタで店舗を選ぶUIを用意
   （Phase 3実装までの代替）。選んだ `store_id` は他画面と同じ `fetchKpiSummary` /
   `fetchDailyStoreSales` にそのまま渡され、自店舗のみのKPI・推移を表示する。
3. **商品企画ビュー**（`ProductPlanningView`）: カテゴリ別売上構成（横棒グラフ、構成比%をツールチップに表示）
   と店舗ランキング（テーブル）を並べて表示。
4. **データ品質ビュー**（`DataQualityView`）: マスター未登録レポート一覧（issue_typeフィルタ付き）、
   quarantine率推移（`Phase3Placeholder`）、「再照合を実行」ボタン（`RequeueButton`、クリックで
   ダミーの実行中→完了表示、実際のジョブは起動しない旨をUI上に明記）。

全画面共通で `store_id` をAPIクエリパラメータとして引き回す設計にしてあり、Phase 3のアクセス制御が
実装された際は「サーバー側で許可された store_id」を渡すだけで動く。

## 表示ロール切替について（重要な注意）

`RoleSwitcher` はこの4画面をデモとして一つのビルドから見せるためのUI上の便宜であり、**アクセス制御では
ない**。コンポーネント内のコメントと画面上の説明文の両方で明記した。実際のデータ可視性は
サーバー側（Unity Catalogのgrant、および将来的にはAPI層でのユーザー×店舗マッピングとの突き合わせ）で
決まる。ロールを切り替えても、APIが返すデータそのものが変わるわけではない。

## チャートライブラリの選定理由（Recharts）

- Reactコンポーネントとして宣言的に書け、TypeScriptの型定義が公式に提供されている。
- 折れ線（日別×店舗推移）・横棒（カテゴリ構成）のどちらも標準コンポーネントで十分に表現でき、
  今回の要件に対して過剰な機能を持つD3直書きや、逆に機能不足になりがちな軽量ライブラリより
  ちょうど良い抽象度。
- `ResponsiveContainer` でダッシュボードのグリッドレイアウトに素直に収まる。
- Databricks Appsの実行環境（Node.js非依存、ビルド時にバンドルされる静的JS/CSS）と相性がよく、
  追加のランタイム依存が発生しない。

## 動作確認

Phase 1同様、このセッションはDatabricksワークスペースへのネットワーク到達性を持たないため、実際の
Warehouse/Gold layerに対する動作確認はできていない。代わりに以下を実施した:

1. `npm run build`（`tsc -b && vite build`）でTypeScriptの型検査とプロダクションビルドが
   エラーなく通ることを確認し、`app/static/` にビルド成果物が生成されることを確認した。
2. `backend/main.py` の `run_query` をモックしたFastAPIサーバーをローカルで起動し、
   ビルド済みSPAとAPIを同一プロセス・同一オリジンで配信させた状態で、Playwright（Chromium）を使い
   実ブラウザで4画面すべてを操作して検証した:
   - 本社経営ダッシュボード: KPIカード・アラート枠・売上推移チャートが表示され、`store_id`/期間
     フィルタと連動することを確認。
   - 店舗ビュー: ログインシミュレーションのセレクタでKPI・チャートのAPI呼び出しに `store_id` が
     渡ることを確認。
   - 商品企画ビュー: カテゴリ別売上構成（横棒グラフ、構成比%表示）と店舗ランキングテーブルの表示を確認。
   - データ品質ビュー: マスター未登録レポートのテーブル表示、issue_typeフィルタのドロップダウン、
     「再照合を実行」ボタンのダミー動作（実行中→ダミー完了メッセージ）を確認。
   - ブラウザのconsoleエラーは `/favicon.ico` への404のみ（`favicon.svg` しか用意していないための
     想定内のブラウザ自動リクエストで、アプリの不具合ではない）。

以上より「Phase 1のAPIから実データを取得して4画面が表示できる」という配線自体は実ブラウザで検証済みだが、
**Gold layerの実データに対する見た目・数値の妥当性は未検証**（Phase 1の「未検証の前提」を参照）。

## Databricks Apps上でのホスティング構成

- `frontend/vite.config.ts` は `build.outDir` を `../app/static` に固定しているため、
  `cd frontend && npm run build` を実行するだけでビルド成果物が `app/static/` に配置される。
- `app/backend/main.py` は起動時に `app/static/` の存在を確認し、存在すればそのディレクトリを
  `StaticFiles(html=True)` として `/` にマウントする（`/api/*` のルートは先に登録済みのため、
  マウントに横取りされない）。これにより **1つのDatabricks App（1つのuvicornプロセス）が
  SPA配信とAPIの両方を兼ねる**ため、CORSやフロントエンド/バックエンドの別ホスティングが不要になる。
- 開発時は `vite.config.ts` の `server.proxy` で `/api` を `http://localhost:8000`
  （`uvicorn backend.main:app --reload` のデフォルト）に転送するため、フロントエンドコードは常に
  相対パス `/api/...` を呼ぶだけでよく、開発時と本番デプロイ後でコードの差異がない。
- デプロイ手順: ①`cd frontend && npm run build`（`app/static/` を生成）→ ②`app/` を
  Databricks Appsとしてデプロイ（`app.yaml` の `command` が `backend.main:app` を起動）。
  `app/static/` はビルド成果物のため `.gitignore` 対象とし、デプロイ前に必ずビルドし直す運用とする。

## このAPI設計・画面構成がユーザー別ニーズにどう対応しているか

- **本社経営（本社営業管理）**: 「今の状況を素早く把握したい」というニーズに対し、KPIカード＋
  前期間比較トグルで増減を一目で（Pastel Green/Coralで）判断できるようにし、日別×店舗チャートで
  変化の内訳を追える構成にした。売上急減アラートの枠を用意し、Phase 3実装後は受動的な通知に
  つなげられる。
- **店長（店舗ビュー）**: 自店舗だけのシンプルな画面にすることで、本社向けの複雑な店舗横断比較UIを
  見せず、自分の店舗の数字だけに集中できるようにした。ログインシミュレーションセレクタはPhase 3までの
  暫定であり、実装後は選択UI自体を撤去してサーバー側の認証情報からstore_idを自動決定する設計にしてある。
- **商品企画**: カテゴリ構成比と店舗ランキングを並べて見せることで、「どのカテゴリを強化すべきか」
  「どの店舗の成功パターンを横展開すべきか」を1画面で行き来しながら検討できるようにした。
- **データサイエンスチーム（データ品質ビュー）**: issue_type別フィルタで問題の種類ごとに追いやすくし、
  quarantine率推移の枠と再照合ボタンを用意することで、単なる一覧閲覧に留まらない運用フロー
  （傾向監視→対処のトリガー）を先取りしたレイアウトにした。

## 次フェーズへの申し送り

- Phase 3で店舗別アクセス制御・アラートAPI・quarantine率API・ジョブトリガーAPIが実装され次第、
  `Phase3Placeholder` / `RequeueButton` / 店舗ビューのログインシミュレーションセレクタを実データ・
  実APIに差し替える。
- Phase 1同様、Gold layerの実カラム名・実データに対する見た目確認はDatabricksワークスペースに
  到達可能な環境で行うこと。
