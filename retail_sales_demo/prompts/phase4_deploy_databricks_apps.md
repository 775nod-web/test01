# Phase 4 プロンプト: Databricks Appsへのデプロイ・README作成

Phase 3 完了後、以下をそのままコーディングエージェントに投入してください。

---

あなたはDatabricksワークスペースに接続されたコーディングエージェントです。`retail_sales_demo/CLAUDE.md` の制約に従い、これまでに実装したServing layerアプリ（バックエンドAPI＋React(TS)フロントエンド）を **Databricks Apps** にデプロイしてください。ローカル環境での起動確認のみで完了とせず、必ずDatabricks Apps上での稼働まで確認すること。

## 実施内容

1. **Databricks Apps上限の再確認**
   - Phase 0時点から状況が変わっている可能性があるため、デプロイ直前に再度Apps数と上限を確認する。
   - 上限に達している場合は `CLAUDE.md` の「Databricks Apps 上限到達時の対応」の手順に厳密に従う。**最も古いアプリの情報を提示し、私の明示的な承認を得てからのみ削除を実行する。**

2. **app.yaml / デプロイ設定**
   - バックエンド起動コマンド、フロントエンドのビルド成果物の配信方法、環境変数（`DATABRICKS_WAREHOUSE_ID=50153ad923fecd73` など）を設定する。
   - アプリのサービスプリンシパルに、対象カタログ/スキーマへのSELECT権限、および再照合ジョブをトリガーするための権限を付与する。

3. **デプロイと疎通確認**
   - Databricks Apps上にデプロイし、URLにアクセスして4画面すべてが正しく表示されること、各APIが実データを返すことを確認する。

4. **README.mdの作成**
   - リポジトリまたはアプリプロジェクトのルートに `README.md` を作成し、以下を含めること:
     - アプリの概要とビジネス目的
     - 前提条件（Serverless Starter Warehouse ID `50153ad923fecd73`、必要なUnity Catalog権限）
     - セットアップ・デプロイ手順
     - デモの操作手順（本社/店長/商品企画/データ品質の各画面の見方）
     - 既知の制約（gross sales暫定値、Free Editionで実装していない範囲）

## 完了条件

- Databricks Apps上のURLで実際にアプリが動作することを確認済みであること。
- README.mdが作成されていること。
- デプロイ完了時に、以下の説明をコードと合わせて出力すること:
  - 最終的な構成図（Gold Delta → Serverless SQL Warehouse → Databricks Apps(API+React) の流れ）
  - この構成がビジネス目的（早期把握・データ品質改善・ガバナンス）を満たす設計になっていることの説明
