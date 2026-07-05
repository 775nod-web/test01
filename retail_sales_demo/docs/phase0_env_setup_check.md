# Phase 0: 環境確認・前提整備 — 結果報告

実施日: 2026-07-05
実行主体: このリポジトリ（775nod-web/test01）に接続されたコーディングエージェントセッション

## 前提として発覚した事実

このリポジトリには実施前時点で `retail_sales_demo/` が存在せず、`CLAUDE.md` / `app/backend/` /
過去フェーズのドキュメントも一切なかった（既存ファイルは無関係な `generate_ecommerce_sample_data.py` /
`save_bronze_delta_tables.py` の2本のみ）。ユーザー確認の上、本フェーズで `retail_sales_demo/CLAUDE.md`・
`app/backend/config.py`・`app/app.yaml`・本ドキュメントを新規に作成した。

## 実行環境の制約（重要）

このコーディングエージェントセッションは **Databricksワークスペースへのネットワーク到達性を持たない**。

- 環境変数 `DATABRICKS_HOST` / `DATABRICKS_TOKEN` は設定されているが、セッションのアウトバウンド通信は
  ポリシー適用プロキシ経由であり、`dbc-74bfd917-30ed.cloud.databricks.com` へのCONNECTはプロキシ側で
  `403`（ポリシー拒否）となり接続不可（`curl` で実測、プロキシの `/__agentproxy/status` でも
  `connect_rejected` として記録）。
- Databricks CLI / `databricks-sdk` もこの環境にインストールされていない。

このため、以下の4項目について **REST API・SQL・CLIによるライブ確認は実施できていない**。
ユーザーの指示により、ライブ検証は行わず、プロンプト記載の前提情報をそのまま採用した上で
未検証である旨を明記して報告する。実際の値の確認は、Databricksワークスペースに到達可能な環境
（Databricksノートブック上のエージェントセッション、またはこのセッションのネットワークポリシーで
当該ホストを許可した場合）で改めて実行する必要がある。

## 確認結果一覧

| # | 項目 | 状態 | 備考 |
|---|------|------|------|
| 1 | Unity Catalog 権限（gold 4テーブル / silver 2テーブルへのSELECT） | **未検証**（ネットワーク不可） | `config.py` / `app.yaml` のデフォルト値（`GOLD_CATALOG=workspace`, `GOLD_SCHEMA=gold`, `SILVER_SCHEMA=silver`）はプロンプト記載の前提と一致させて作成済み |
| 2 | Serverless SQL Warehouse（ID: `50153ad923fecd73`）の存在・起動可否・CAN_USE権限 | **未検証**（ネットワーク不可） | `app.yaml` / `config.py` に `SQL_WAREHOUSE_ID` として設定済み |
| 3 | Databricks Apps 件数・上限到達有無 | **未検証**（ネットワーク不可） | — |
| 4 | ユーザー/店舗マッピングデータの有無 | **未確認**（ネットワーク不可のため既存有無を調査できず） | 存在しない場合はデモ用の簡易マッピングテーブルを新規作成する前提で進める（ユーザー承認済み、下記参照） |

## 各項目の詳細と、ライブ環境で実行すべき確認コマンド

### 1. Unity Catalog 権限確認

Databricksに接続可能な環境で以下を実行して確認する:

```sql
SHOW GRANTS ON TABLE workspace.gold.gold_daily_store_sales;
SHOW GRANTS ON TABLE workspace.gold.gold_category_sales;
SHOW GRANTS ON TABLE workspace.gold.gold_store_ranking;
SHOW GRANTS ON TABLE workspace.gold.gold_unregistered_master_report;
SHOW GRANTS ON TABLE workspace.silver.silver_product_master;
SHOW GRANTS ON TABLE workspace.silver.silver_store_master;
```

または REST API: `GET /api/2.1/unity-catalog/permissions/table/{full_name}`。

`app/backend/config.py` のデフォルト（`workspace.gold` / `workspace.silver`）は、プロンプトに記載の
確認済み情報と一致させてある。実環境と異なる場合は環境変数 `GOLD_CATALOG` / `GOLD_SCHEMA` /
`SILVER_SCHEMA` で上書きする。

### 2. Serverless SQL Warehouse確認

```
GET /api/2.0/sql/warehouses/50153ad923fecd73
GET /api/2.0/permissions/warehouses/50153ad923fecd73
```

または `databricks warehouses get 50153ad923fecd73` / `databricks warehouses get-permissions 50153ad923fecd73`。
State（`RUNNING` / `STOPPED` など）と、実行ユーザー/サービスプリンシパルに `CAN_USE` 権限が
付与されているかを確認する。

### 3. Databricks Apps 上限確認

```
GET /api/2.0/apps
```

または `databricks apps list`。件数とワークスペースの上限を突き合わせ、上限到達時は作成日時が
古い順にソートしてアプリ名・作成者・作成日時を一覧化し、ユーザーに削除可否を確認する
（**ユーザー承認なしに削除しない**）。

### 4. ユーザー/店舗マッピングデータの有無確認

既存のマッピング実体（テーブル、SCIMグループ、Unity Catalogのgroup権限など）を以下のような方法で
確認する:

- `information_schema.tables` / `SHOW TABLES IN workspace.silver` 等でマッピングらしき命名のテーブルを検索
- SCIMグループAPI (`GET /api/2.0/preview/scim/v2/Groups`) で店舗単位のグループが存在するか確認

**本セッションではこの調査を実行できていない。** ユーザーからは「存在しない場合はデモ用の簡易マッピング
テーブルを新規作成する」方針で承認済み。ライブ確認の結果、既存マッピングが見つからなければ、Phase 1で
`workspace.silver.silver_user_store_mapping`（例: `user_email STRING, store_id STRING`）のような
簡易テーブルを新規作成する想定で進める。

## 次フェーズへの申し送り

- 上記1〜4は次にDatabricksワークスペースへの到達性がある環境（Databricksノートブック上のエージェント
  セッション等）で実測し、本ドキュメントを更新すること。
- `phase1_serving_layer_api.md` は未提示のため、提示され次第着手する。
