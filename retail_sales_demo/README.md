# retail_sales_demo — 小売POS売上分析デモ

## 概要とビジネス目的

Databricks Gold layer（Bronze/Silver/Goldパイプラインは既存・本プロジェクトのスコープ外）を
Serving layer（REST API + React SPA、Databricks Appsでホスト）として社内公開するデモアプリ。
以下3つの業務課題への対応を目的とする。

- **早期把握**: 店舗別・カテゴリ別の売上をリアルタイムに近い形でダッシュボード表示し、
  売上急減を日次バッチで自動検知してアラート表示する。
- **データ品質改善**: マスター未登録取引（quarantine）をissue_type別に可視化し、
  マスタ更新後に再照合すべき候補件数を自動検出する。
- **ガバナンス**: 店舗別アクセス制御・PIIマスキング・監査ログにより、「誰が・どの店舗の・
  どんなデータを見られるか／見たか」を制御・追跡できるようにする。

対象ユーザーと画面の対応は以下の4画面（詳細は「デモの操作手順」参照）:

| 画面 | 対象ユーザー |
|---|---|
| 本社経営ダッシュボード | 本社営業管理 |
| 店舗ビュー | 店長 |
| 商品企画ビュー | 商品企画 |
| データ品質ビュー | データサイエンスチーム |

## 前提条件

- **Unity Catalog**: `workspace.gold`（`gold_daily_store_sales` / `gold_category_sales` /
  `gold_store_ranking` / `gold_unregistered_master_report`、Phase 3以降は
  `gold_store_sales_alerts` / `gold_requeue_batch_runs` も）と `workspace.silver`
  （`silver_product_master` / `silver_store_master`、Phase 3以降は
  `silver_user_store_mapping` / `silver_user_role_mapping` / `silver_app_audit_log` も）に
  実データが投入済みであること。
- **Serverless SQL Warehouse**: Warehouse ID `50153ad923fecd73`
  （Serverless Starter Warehouse）が起動可能で、アプリのサービスプリンシパルに `CAN_USE` 権限が
  付与されていること。
- **権限**: アプリのサービスプリンシパルに、上記テーブルへの `SELECT`（監査ログテーブルのみ
  `SELECT, MODIFY`）が付与されていること。テンプレート: `sql/004_app_service_principal_grants.sql`。
- Node.js 22系、Python 3.11系（ローカルでビルド・テストする場合）。

## セットアップ・デプロイ手順

> **注意**: このリポジトリを作成したセッションはDatabricksワークスペースへのネットワーク到達性を
> 持たず、以下の手順は実際には実行・検証できていない。Databricksワークスペースに到達可能な環境で
> 実施し、`docs/phase4_deployment.md` に結果を追記すること。

1. **ガバナンステーブルの作成**: `sql/001_user_store_mapping.sql` 〜
   `sql/003_app_audit_log.sql` を実行し、`user_email` を実際のユーザーに合わせて調整する。
2. **フロントエンドのビルド**:
   ```bash
   cd frontend
   npm install
   npm run build   # ../app/static に出力（FastAPIが配信する）
   ```
3. **Databricks Appの作成**（`databricks apps create` またはUI）し、
   Serverless Starter Warehouse（`50153ad923fecd73`）をリソースとして接続する。
4. **権限付与**: アプリ作成後に判明するサービスプリンシパルIDで
   `sql/004_app_service_principal_grants.sql` の `<APP_SERVICE_PRINCIPAL>` を置き換えて実行する。
5. **デプロイ**: `app/` ディレクトリ（`app.yaml` を含む）をアプリのソースとしてデプロイする
   （`databricks apps deploy`）。
6. **（任意）バッチジョブのデプロイ**: `jobs/resources/alert_batch_job.json` /
   `requeue_batch_job.json` をデプロイし、`requeue_batch_job` のjob_idを `app/app.yaml` の
   `REQUEUE_JOB_ID` に設定して再デプロイすると、「再照合を実行」ボタンが実際にジョブを起動する
   ようになる（未設定の間はHTTP 501でその旨を明示的に返す）。
7. **疎通確認**: 発行されたURLにアクセスし、4画面が表示され各APIが実データを返すことを確認する。

ローカルで動作確認する場合:
```bash
cd app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABRICKS_HOST=... DATABRICKS_TOKEN=... uvicorn backend.main:app --reload
```
バックエンドのユニット/APIテストのみ（Databricks接続不要）:
```bash
cd app && source .venv/bin/activate && python -m pytest backend/tests
```

## デモの操作手順

画面上部の「表示ロール切替」で4画面を切り替えられる。**これは見せ方を切り替えるだけのデモ用UIで、
実際のアクセス制御はサーバー側で行われる**（店舗ビュー・データ品質ビューの「ログインシミュレーション
／実行ユーザー」セレクタが、実際にサーバー側へ送る識別子を切り替える）。

1. **本社経営ダッシュボード**: 店舗・期間で絞り込みながらKPI（net/gross sales・取引件数・
   販売点数・平均バスケットサイズ）と日別×店舗の売上推移を確認する。「前期間と比較」で
   増減率をKPIカードの色（緑=増加/コーラル=減少）で確認できる。売上急減アラートは
   `jobs/alert_batch.py` の日次実行結果を表示する。
2. **店舗ビュー**: 「ログインシミュレーション」で店長の識別子を切り替えると、その店舗のみの
   KPI・売上推移が表示される（サーバー側の店舗別アクセス制御によるもの）。
3. **商品企画ビュー**: カテゴリ別売上構成（構成比%付き）と店舗ランキングを確認する。
4. **データ品質ビュー**: 「実行ユーザー」を切り替えると、マスター未登録レポートの顧客IDが
   PII_VIEWERロールの有無に応じてマスク表示/非表示になることと、監査ログパネルが
   AUDIT_VIEWERロールの有無に応じて閲覧可否が変わることを確認できる。「再照合を実行」ボタンで
   quarantine再照合バッチ（`REQUEUE_JOB_ID` 未設定時はその旨のメッセージ）をトリガーできる。

## 既知の制約

- **gross salesは暫定値**: `gold_daily_store_sales` / `gold_category_sales` に discount
  集約列が無いため、`gross_sales` は `net_sales` と同値で返す（`gross_sales_is_estimated: true`
  で明示）。正確な算出にはGold layerへのdiscount集約列の追加が必要（Phase 1参照）。
- **Free Editionで未検証・未実装の範囲**（Phase 3参照）:
  - 店舗別アクセス制御・PIIマスキングは、Unity Catalogの行フィルタ／列マスクではなく
    APIレイヤーでのフォールバック実装。単一の共有サービスプリンシパルでWarehouseに接続しているため、
    DB直アクセスにはこのアクセス制御は及ばない。
  - 監査ログは `system.access.audit` ではなく、アプリ独自の軽量テーブルへのフォールバック実装。
  - 売上急減アラート・quarantine再照合の各バッチジョブ（`jobs/`）はコードとJobs API用JSON
    テンプレートまでは用意したが、実際のワークスペースへのデプロイ・実行は未検証（Phase 3/4参照）。
- **スキーマの前提は未検証**: Gold/Silverの各テーブルの実際の列名は、このプロジェクトを作成した
  セッションがDatabricksワークスペースに到達できなかったため確認できていない
  （`app/backend/schema_assumptions.py` に前提を明記、`DESCRIBE TABLE` での確認が必要）。
- **Databricks Apps上のURLでの実際の動作確認は未実施**（Phase 4参照）。ローカルではモックした
  接続とPlaywrightによるブラウザ検証のみ実施済み。

## ドキュメント一覧

各フェーズの詳細な実施内容・申し送り事項は `docs/` 配下を参照:

- `docs/phase0_env_setup_check.md` — 環境確認
- `docs/phase1_serving_layer_api.md` — バックエンドAPI
- `docs/phase2_frontend.md` — フロントエンド
- `docs/phase3_governance_and_ops.md` — ガバナンス・アラート・再照合バッチ
- `docs/phase4_deployment.md` — デプロイ・構成図
