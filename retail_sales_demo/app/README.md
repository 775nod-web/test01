# 小売POS売上分析デモ — Serving Layer アプリケーション

Gold layer（Unity Catalog上のDelta テーブル）を、TypeScript + ReactのUIから閲覧できるようにするServing layerの実装です。デザイン・優先度・アーキテクチャの説明は `../README.md` と `../CLAUDE.md` を参照してください。

> **このコードはDatabricksワークスペースに未接続の状態で作成されています。** カタログ/スキーマ名、Databricks SDKのレスポンス構造、`app.yaml`の記法などは仮定・一般的な仕様に基づいており、実際のワークスペースで動作確認・調整が必要です。下記「デプロイ前チェックリスト」を必ず確認してください。

## 構成

```
app/
  backend/          # FastAPI バックエンド（Serverless SQL Warehouse経由でGoldテーブルを参照）
  frontend/         # React + TypeScript フロントエンド（Vite）
  sql/              # ガバナンス設定（行フィルタ・列マスキング）とテーブル作成DDL
  jobs/             # Databricks Jobs用バッチ（売上急減アラート／quarantine再照合）
  resources/jobs.yml# Databricks Asset Bundles ジョブ定義例
  app.yaml          # Databricks Apps 設定
```

## セットアップ・デプロイ手順

### 1. 前提リソースの作成（Databricksワークスペース側）

Databricks SQLエディタ等で以下を実行する（`${catalog}` `${schema}` は実際の値に置換）。

```
sql/01_user_store_mapping.sql   -- 必須: ユーザー×店舗マッピング表を作成
sql/02_row_filter_store_access.sql  -- 任意: UC行フィルタが使える場合（Free Editionで要検証）
sql/03_column_mask_pii.sql      -- 必須: customer_idの列マスキング
sql/04_alerts_table.sql         -- 必須: アラート出力先テーブル
sql/05_audit_log_table.sql      -- 任意: system.access.auditが使えない場合のフォールバック
```

### 2. Databricks Jobsの作成

`resources/jobs.yml` を参考に、`jobs/sales_drop_alert_job.py`（日次アラート算出）と `jobs/quarantine_reconciliation_job.py`（quarantine再照合）をDatabricks Jobsとして登録する。作成後、quarantine再照合ジョブのJob IDを控えておく。

### 3. バックエンドの環境変数設定

`app.yaml` の `env` を実環境に合わせて編集する。

| 変数 | 説明 |
|---|---|
| `DATABRICKS_WAREHOUSE_ID` | `50153ad923fecd73`（変更不要） |
| `GOLD_CATALOG` / `GOLD_SCHEMA` | Gold layerテーブルの実際のカタログ/スキーマ名 |
| `SALES_DROP_ALERT_THRESHOLD_PCT` | アラートしきい値（%） |
| `RECONCILE_JOB_ID` | 手順2で作成したquarantine再照合ジョブのJob ID |
| `ROW_FILTER_ENABLED_BY_UC` | UC行フィルタが有効な場合は `true`、フォールバック運用の場合は `false` |

### 4. フロントエンドのビルド

```bash
cd frontend
npm install
npm run build
```

`frontend/dist/` にビルド成果物が生成され、`backend/main.py` がこれを静的配信する。

### 5. Databricks Appsへのデプロイ

Databricks CLIから、このディレクトリ（`app/`）をソースとしてDatabricks Appsにデプロイする。上限に達している場合の対応は `../CLAUDE.md` の「Databricks Apps 上限到達時の対応」に従うこと（**削除前に必ずユーザー確認**）。

```bash
databricks apps deploy <app-name> --source-code-path .
```

（コマンドオプションは実際のCLIバージョンに合わせて確認すること。）

## デプロイ前チェックリスト（未接続で作成したため要検証）

- [ ] `GOLD_CATALOG` / `GOLD_SCHEMA` が実環境の値になっているか
- [ ] 4つのGoldテーブルが実際にそのカタログ/スキーマに存在し、SELECT権限があるか
- [ ] Warehouse `50153ad923fecd73` が起動可能で、CAN_USE権限があるか
- [ ] `backend/db.py` のDatabricks SDK Statement Execution API呼び出しが、実際のSDKバージョンのレスポンス構造と一致しているか
- [ ] UC行フィルタ（`sql/02_row_filter_store_access.sql`）がFree Editionで動作するか。動作しない場合は `ROW_FILTER_ENABLED_BY_UC=false` のままAPI側フィルタで運用する
- [ ] `system.access.audit` が参照可能か。不可の場合は `sql/05_audit_log_table.sql` のフォールバックを使う
- [ ] `app.yaml` の記法が現行のDatabricks Apps仕様と一致しているか

## デモ操作手順

1. 起動後、画面右上のロール切替（本社経営／店長／商品企画／データ品質）で4つの画面を切り替えられる。
2. 本社経営画面: KPIサマリー、日別売上推移、売上急減アラートバナーを確認する。
3. 店長画面: 自店舗のみに絞り込まれたデータが表示されることを確認する（アクセス制御のデモ）。
4. 商品企画画面: カテゴリ別売上構成と店舗ランキングを確認する。
5. データ品質画面: quarantine率の推移と未登録取引一覧を確認し、「再照合を実行」ボタンでジョブがトリガーされることを確認する。

## 既知の制約

- KPIの `gross_sales` は、Gold layerにdiscount集約列が無いため `net_sales` と同値の暫定値です（`gross_sales_is_estimated: true` で明示）。
- quarantine再照合ジョブは、対象件数の可視化とログ記録までを行い、実際のGold再計算（quarantineからの昇格）は既存のSilver→Goldパイプライン側の改修が別途必要です。
