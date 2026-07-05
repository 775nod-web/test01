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
- バックエンド設定: `app/backend/config.py`（`GOLD_CATALOG` / `GOLD_SCHEMA` / `SILVER_SCHEMA` / `DATABRICKS_WAREHOUSE_ID` を環境変数で上書き可能）
- デプロイ設定: `app/app.yaml`
- ガバナンス関連テーブル（Phase 3、DDL: `sql/`）: `workspace.silver.silver_user_store_mapping` / `silver_user_role_mapping` / `silver_app_audit_log`、`workspace.gold.gold_store_sales_alerts` / `gold_requeue_batch_runs`（バッチジョブ: `jobs/`）

## デザイントークン

フロントエンドは以下をCSS変数として定義し、全画面で統一して使用する（Phase 2で新規策定。淡い配色＋
Off White背景の落ち着いたダッシュボードトーンを想定）。

| トークン名 | 用途 | 値 |
|---|---|---|
| `--color-bg` | 画面背景 (Off White) | `#FAF9F6` |
| `--color-surface` | カード等の背景 | `#FFFFFF` |
| `--color-text` | 本文濃色テキスト | `#2B2B2B` |
| `--color-text-muted` | 補助テキスト | `#6B7280` |
| `--pastel-blue` | 情報・中立、店舗系アクセント | `#AFC9E9` |
| `--pastel-green` | ポジティブな数値変化 | `#B8E0C7` |
| `--pastel-coral` | ネガティブな数値変化・警告 | `#F3B7AE` |
| `--pastel-yellow` | 注意・暫定値バッジ | `#F5E3A1` |
| `--pastel-purple` | 商品企画系アクセント | `#D3C5EA` |

KPIカードは「淡色背景（パステル）＋濃色テキスト（`--color-text`）」を基本構成とし、数値変化の符号に応じて
背景を `--pastel-green`（増加）/ `--pastel-coral`（減少）に切り替える。

## フェーズ

1. **Phase 0 — 環境確認**（`docs/phase0_env_setup_check.md`）: UC権限・Warehouse・Databricks Apps上限・ユーザー/店舗マッピングの有無を確認する。コード実装は行わない。
2. **Phase 1 — Serving layer API**（`docs/phase1_serving_layer_api.md`）: Phase 0の確認結果を踏まえてバックエンドAPIを実装する。
3. **Phase 2 — フロントエンド**（`docs/phase2_frontend.md`）: TypeScript + React (Vite) で4画面のダッシュボードを実装する。Streamlitは使用しない。
4. **Phase 3 — ガバナンス・アラート・自動再照合**（`docs/phase3_governance_and_ops.md`）: 店舗別アクセス制御・PIIマスキング・監査ログ（いずれもUCネイティブ機能が検証できずAPIレイヤーのフォールバックを採用）、売上急減アラートバッチ、quarantine再照合バッチを実装する。
5. **Phase 4 — デプロイ・README**（`docs/phase4_deployment.md`）: Databricks Appsへのデプロイと、READMEの作成。

## 制約

- 各フェーズの確認・実装内容は `docs/` 配下にドキュメントとして残すこと。
- 破壊的操作（Databricks Appsの削除など）は必ずユーザーの承認を得てから実行すること。承認前に実行しない。
- 店舗別アクセス制御（どのユーザーがどの店舗のデータを見られるか）を実装する場合、そのためのユーザー/店舗マッピングの実体（テーブル・グループ等）が存在するかをPhase 0で確認し、存在しない場合はデモ用の簡易マッピングを作る前提でユーザーに確認すること。

## Databricks Apps 上限到達時の対応

デプロイ前に必ずApps数と上限を確認する。上限に達している場合:

1. 作成済みApps一覧を作成日時の昇順で取得する。
2. 最も作成日時が古いアプリについて、**名前・作成者・作成日時**を一覧化してユーザーに提示する。
3. ユーザーの明示的な承認を得るまで、いかなるアプリも削除しない。承認が得られたら、指定されたアプリのみ削除する。
4. 承認が得られない場合は、削除せずにユーザーの判断を待つ（別ワークスペース/上限緩和の相談など、削除以外の代替案も提示してよい）。
