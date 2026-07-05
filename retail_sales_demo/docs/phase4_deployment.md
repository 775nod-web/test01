# Phase 4: Databricks Appsへのデプロイ・README作成 — 結果報告

実施日: 2026-07-05

## できなかったこと（重要）

このコーディングエージェントセッションは、Phase 0以降一貫してDatabricksワークスペースへの
ネットワーク到達性を持たない（セッションのエグレスポリシーが `dbc-74bfd917-30ed.cloud.databricks.com`
へのCONNECTを403で拒否。本フェーズ開始時にも `GET /api/2.0/apps` で再確認済み、結果は同じ403）。

このため、本フェーズの完了条件である以下は **実施できていない**:

- Databricks Apps数・上限の再確認
- 実際のDatabricks Appsへのデプロイ
- デプロイ後のURLへのアクセス、4画面の表示確認、各APIが実データを返すことの確認
- アプリのサービスプリンシパルへの実際の権限付与

**したがって「Databricks Apps上のURLで実際にアプリが動作することを確認済みである」という完了条件は
満たせていない。** 以下は、それ以外にこのセッションから準備できるものをすべて用意した結果であり、
実際のデプロイ・疎通確認はDatabricksワークスペースに到達可能な環境（Databricksノートブック上の
エージェントセッション等）で改めて行う必要がある。

## このセッションで準備したもの

1. **デプロイ設定の最終化**: `app/app.yaml` に `DATABRICKS_WAREHOUSE_ID` /
   `DEMO_USER_EMAIL` を設定済み、`REQUEUE_JOB_ID` はジョブデプロイ後に設定するプレースホルダを
   コメントで用意。`command` はビルド済みフロントエンド（`app/static/`）とAPIの両方を1プロセスで
   提供する構成（Phase 2で確立済み）。
2. **権限付与SQLのテンプレート**: `sql/004_app_service_principal_grants.sql` に、
   アプリのサービスプリンシパルに必要な `USE CATALOG` / `USE SCHEMA` / `SELECT` /
   （監査ログ用の）`MODIFY`、およびWarehouseのCAN_USE・Jobsの実行権限を付与するコマンドの
   テンプレートを用意（`<APP_SERVICE_PRINCIPAL>` はアプリ作成後に判明する値のプレースホルダ）。
3. **`CLAUDE.md` に「Databricks Apps 上限到達時の対応」手順を明文化**: このフェーズのプロンプトが
   参照していたが実際には存在しなかったため、Phase 0プロンプトの指示内容に基づいて新規に追記した
   （最古のアプリの名前・作成者・作成日時を提示し、ユーザーの明示的承認なしに削除しない、という手順）。
4. **README.md**: リポジトリ内 `retail_sales_demo/README.md` に、概要・前提条件・セットアップ手順・
   デモの操作手順・既知の制約を記載（詳細は同ファイル参照）。
5. 既存のテスト・ビルドを再実行し、デプロイ可能な状態であることを再確認: バックエンド
   `pytest`（42件）、フロントエンド `npm run build`（`app/static/` 生成）がいずれも成功することを
   このセッションで再確認済み。

## Databricksワークスペースに到達可能な環境で実施すべき手順（未実施分）

1. **Apps上限の再確認**: `GET /api/2.0/apps` で件数を確認。上限到達時は
   `CLAUDE.md`「Databricks Apps 上限到達時の対応」に従い、最古のアプリ情報をユーザーに提示し
   承認を得てから削除する。
2. **Unity Catalog前提の再確認**: `sql/001`〜`003`（Phase 3のマッピング/監査ログテーブル）を実行し、
   `sql/004`（本フェーズの権限付与）は `<APP_SERVICE_PRINCIPAL>` を実際の値に置き換えてから実行する
   （サービスプリンシパルIDはアプリ作成後でないと判明しないため、アプリ作成→サービスプリンシパル確認
   →`004`実行、の順になる）。
3. **アプリの作成**: `databricks apps create` （または UI）で `retail_sales_demo` アプリを作成し、
   Serverless Starter Warehouse（`50153ad923fecd73`）をリソースとして接続する。
4. **フロントエンドのビルド**: `cd frontend && npm run build`（`app/static/` に出力）。
5. **デプロイ**: `databricks apps deploy` で `app/` をソースとしてデプロイ。
6. **疎通確認**: 発行されたURLにアクセスし、4画面（本社/店長/商品企画/データ品質）が表示され、
   各APIが実データを返すことを確認する。特に以下を確認する:
   - `X-Forwarded-Email` ヘッダーが実際にSSOユーザーのメールアドレスで来ているか
     （`access_control.py` の前提— 未検証。ヘッダー名が異なる場合は同ファイルの `_HEADER_NAME` を修正）。
   - `gold_unregistered_master_report` に実際に `customer_id` 列が存在するか
     （`schema_assumptions.py` の前提 — 存在しない場合はPIIマスキング機能自体を無効化する必要がある）。
7. **バッチジョブのデプロイ**（Phase 3の申し送り事項）: `jobs/resources/alert_batch_job.json` /
   `requeue_batch_job.json` をデプロイし、`requeue_batch_job` のjob_idを `REQUEUE_JOB_ID` 環境変数に
   設定してアプリを再デプロイする。
8. 上記すべてが完了したら、本ドキュメントに実施結果（URL、確認したスクリーンショット等）を追記する。

## 最終構成図

```
[Bronze/Silver/Gold パイプライン]（既存、本プロジェクトのスコープ外）
        │
        ▼
workspace.gold.gold_daily_store_sales / gold_category_sales /
                gold_store_ranking / gold_unregistered_master_report
workspace.silver.silver_product_master / silver_store_master
workspace.silver.silver_user_store_mapping / silver_user_role_mapping / silver_app_audit_log   (Phase 3)
workspace.gold.gold_store_sales_alerts / gold_requeue_batch_runs                                (Phase 3 batch出力)
        │  (Delta Lake / Unity Catalog)
        ▼
Serverless SQL Warehouse (50153ad923fecd73)
        │  databricks-sql-connector（NATIVEパラメータバインド）
        ▼
Databricks Apps: retail_sales_demo
  ├─ FastAPIバックエンド (app/backend/main.py)
  │    ├─ /api/kpi-summary, /api/daily-store-sales, /api/category-sales,
  │    │  /api/store-ranking, /api/quarantine-report   (Phase 1)
  │    ├─ /api/me, /api/alerts, /api/audit-log,
  │    │  /api/requeue-status, /api/requeue-trigger    (Phase 3)
  │    ├─ access_control.py: X-Forwarded-Emailベースの店舗別アクセス制御・PIIマスキング
  │    └─ audit.py: 全/api/*アクセスをsilver_app_audit_logへ記録
  └─ React(TS) SPA (frontend/ → app/static/、同一プロセスから配信)
       ├─ 本社経営ダッシュボード（KPI・売上推移・アラートバナー）
       ├─ 店舗ビュー（自店舗のみ、ログインシミュレーション）
       ├─ 商品企画ビュー（カテゴリ構成・店舗ランキング）
       └─ データ品質ビュー（quarantineレポート・監査ログ・再照合トリガー）
        │
        ▼ (Jobs API: run-now)
Databricks Jobs
  ├─ jobs/alert_batch.py      （日次、DoD/WoW売上急減検知 → gold_store_sales_alerts）
  └─ jobs/requeue_batch.py    （オンデマンド、再照合候補検出 → gold_requeue_batch_runs）
```

## この構成がビジネス目的をどう満たすか

- **早期把握**: Gold Delta（店舗別・カテゴリ別・日次の事前集計）をServerless SQL Warehouse経由で
  そのままAPI化しているため、本社ダッシュボードは追加のバッチ処理を待たずに最新のGoldデータを
  即座に反映する。売上急減アラート（`gold_store_sales_alerts`）は日次バッチで機械的に生成され、
  ダッシュボードに常時表示されるため、人が気づくのを待たずに異常を検知できる。
- **データ品質改善**: `gold_unregistered_master_report` をissue_type別に閲覧できるデータ品質ビューと、
  再照合候補を自動検出する `requeue_batch.py` により、マスター未登録取引の発見から
  「再照合の価値があるか」の判断までの導線を1画面に集約した。
- **ガバナンス**: 店舗別アクセス制御・PIIマスキング・監査ログをAPIレイヤーに実装し
  （Unity Catalogネイティブ機能は未検証のためフォールバック、Phase 3参照）、「誰が・いつ・何を見たか」を
  追跡可能にした。Databricks Apps自体がサービスプリンシパル単位でUnity Catalogの権限管理下に置かれる
  ため、`sql/004` の権限付与によりアプリがアクセスできる範囲そのものも最小権限の原則に沿って絞り込める。

以上の設計は、Gold layerの実データ・実権限に対して検証されて初めて「動作する」と言えるものであり、
本フェーズではその検証（デプロイ・疎通確認）ができていない点を改めて明記する。
