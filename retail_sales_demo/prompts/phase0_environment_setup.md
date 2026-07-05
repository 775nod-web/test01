# Phase 0 プロンプト: 環境確認・前提整備

以下をそのままDatabricksワークスペースに接続されたコーディングエージェントに投入してください。

---

あなたはDatabricksワークスペースに接続されたコーディングエージェントです。`retail_sales_demo/CLAUDE.md` の制約に従い、小売POS売上分析デモのServing layer実装に着手する前の環境確認を行ってください。コードの実装はまだ行わず、確認と報告のみ行ってください。

## 前提（確認済み情報）

Gold layerは `workspace.gold` スキーマ（`gold_daily_store_sales` / `gold_category_sales` / `gold_store_ranking` / `gold_unregistered_master_report`）、マスターは `workspace.silver` スキーマ（`silver_product_master` / `silver_store_master`）に実データが投入済みであることを確認済み（店舗5件・カテゴリ4件・POS取引230件・マスター未登録10件）。以下ではこの前提の上で、権限面と実行環境を確認する。

## 実施内容

1. **Unity Catalog の権限確認**
   - `workspace.gold` の4テーブル、`workspace.silver` の2マスターテーブルに対する、自分（サービスプリンシパル/実行ユーザー）のSELECT権限があるか確認する。
   - `retail_sales_demo/app/backend/config.py` および `app.yaml` のデフォルト値（`GOLD_CATALOG=workspace`, `GOLD_SCHEMA=gold`, `SILVER_SCHEMA=silver`）がこの環境と一致していることを再確認する。

2. **Serverless SQL Warehouseの確認**
   - Warehouse ID `50153ad923fecd73`（Serverless Starter Warehouse）が存在し、起動可能な状態か確認する。
   - この Warehouse に対する CAN_USE 権限があるか確認する。

3. **Databricks Apps の上限確認**
   - 現在のワークスペースで作成済みのDatabricks Apps一覧を取得し、件数と上限に達しているかを確認する。
   - 上限に達している場合は、作成日時が最も古いアプリの名前・作成者・作成日時を一覧化して私に提示し、削除してよいかの承認を求める。**私の承認なしに削除を実行しないこと。**

4. **想定ユーザー/店舗マッピングデータの有無確認**
   - 店舗別アクセス制御を実装するために必要な「どのユーザーがどの店舗を担当するか」のマッピング情報（テーブル、グループ、または何らかのマスタ）が既存workspace内に存在するか確認する。存在しない場合は、デモ用に簡易マッピングテーブルを新規作成する前提で良いか私に確認する。

## 完了条件

- 上記4項目の確認結果を一覧で報告する。
- 不明点・存在しないリソースがあれば、実装方針（作成する/代替案を使う）を提案し、私の承認を得てから次フェーズ(`phase1_serving_layer_api.md`)に進む。
