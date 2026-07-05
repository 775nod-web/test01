# Phase 2 プロンプト: フロントエンド（TypeScript + React）実装

Phase 1 完了後、以下をそのままコーディングエージェントに投入してください。

---

あなたはDatabricksワークスペースに接続されたコーディングエージェントです。`retail_sales_demo/CLAUDE.md` のデザイントークンと制約に従い、Phase 1で実装したAPIを利用するフロントエンドを **TypeScript + React（Vite）** で実装してください。**Streamlitは使用しないこと。**

## 実装する画面

1. **本社経営ダッシュボード**（本社営業管理向け）
   - KPIサマリーカード（net sales / gross sales(暫定) / transaction count / units sold / average basket size）
   - 日別×店舗の売上推移チャート（`gold_daily_store_sales`）
   - 売上急減アラートバナー（Phase 3実装のアラートAPIに接続、未実装時はダミーで枠のみ用意）

2. **店舗ビュー**（店長向け）
   - ログインユーザーに紐づく自店舗のデータのみを表示（Phase 3のアクセス制御と連動する前提でUIを組む。実装時点でバックエンドが未対応でもフィルタ用のUI/APIパラメータは用意しておく）

3. **商品企画ビュー**（商品企画向け）
   - カテゴリ別売上構成（`gold_category_sales`）
   - 店舗ランキング（`gold_store_ranking`）

4. **データ品質ビュー**（データサイエンスチーム向け）
   - マスター未登録レポート一覧（`gold_unregistered_master_report`、issue_typeフィルタ付き）
   - quarantine率推移（Phase 3実装予定、未実装時はダミー枠）
   - 「再照合を実行」ボタン（Phase 3のジョブトリガーAPIに接続、未実装時はダミー）

## デザイン要件

- `CLAUDE.md` のデザイントークン（Pastel Blue/Green/Coral/Yellow/Purple、Off White背景）をCSS変数として定義し、全画面で統一して使用する。
- KPIカードは淡色背景＋濃色テキストの構成とし、ポジティブ/ネガティブな数値変化には Pastel Green / Pastel Coral を用いる。
- デモの利便性のため、画面上部に「表示ロール切替（本社／店長／商品企画／データ品質）」のセレクタを設ける。**これはデモの見せ方を切り替えるためのUI上の便宜であり、実際のアクセス制御はサーバー側（Unity Catalog / API）で行う旨をコード内コメントと説明文で明記すること。**

## 完了条件

- 4画面が実装され、Phase 1のAPIからデータを取得して表示できることを確認する。
- チャートライブラリ（例: Recharts）の選定理由を簡潔に記録する。
- 実装完了時に、以下の説明をコードと合わせて出力すること:
  - 画面構成がユーザー別（本社/店長/商品企画/DSチーム）のニーズにどう対応しているか
  - Databricks Apps上でReact(TS)アプリをホストする構成の概要（ビルド成果物の配置、APIとの通信方式）
