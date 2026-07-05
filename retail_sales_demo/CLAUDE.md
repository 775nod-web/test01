# retail_sales_demo — 小売POS売上分析デモ

Databricks上に構築する小売POS売上分析デモ。Bronze/Silver/Gold の各レイヤーはすでに整備済みで、
このプロジェクトのスコープは **Serving layer**（Databricks Apps 上のバックエンドAPI + フロントエンド）の実装。

## データ基盤（前提）

- Gold layer: `workspace.gold` スキーマ
  - `gold_daily_store_sales`
  - `gold_category_sales`
  - `gold_store_ranking`
  - `gold_unregistered_master_report`
- Silver master: `workspace.silver` スキーマ
  - `silver_product_master`
  - `silver_store_master`

上記はUnity Catalog上に実データ投入済み（店舗5件・カテゴリ4件・POS取引230件・マスター未登録10件、2026-07-05時点でのフェーズ0確認により確認）。

## 実行環境

- SQL実行: Serverless SQL Warehouse（Warehouse ID: `50153ad923fecd73`, Serverless Starter Warehouse）
- ホスティング: Databricks Apps
- バックエンド設定: `app/backend/config.py`（`GOLD_CATALOG` / `GOLD_SCHEMA` / `SILVER_SCHEMA` / `SQL_WAREHOUSE_ID` を環境変数で上書き可能）
- デプロイ設定: `app/app.yaml`

## フェーズ

1. **Phase 0 — 環境確認**（`docs/phase0_env_setup_check.md`）: UC権限・Warehouse・Databricks Apps上限・ユーザー/店舗マッピングの有無を確認する。コード実装は行わない。
2. **Phase 1 — Serving layer API**（`docs/phase1_serving_layer_api.md`、別プロンプトで提示予定）: Phase 0の確認結果を踏まえてバックエンドAPIを実装する。

## 制約

- 各フェーズの確認・実装内容は `docs/` 配下にドキュメントとして残すこと。
- 破壊的操作（Databricks Appsの削除など）は必ずユーザーの承認を得てから実行すること。承認前に実行しない。
- 店舗別アクセス制御（どのユーザーがどの店舗のデータを見られるか）を実装する場合、そのためのユーザー/店舗マッピングの実体（テーブル・グループ等）が存在するかをPhase 0で確認し、存在しない場合はデモ用の簡易マッピングを作る前提でユーザーに確認すること。
