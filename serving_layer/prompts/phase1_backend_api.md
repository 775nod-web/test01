# Phase 1: Backend API プロンプト

`serving_layer/CLAUDE.md` を読み込んだ上で、以下を実施してください。

## ゴール

Gold layer の4テーブル（`gold.daily_kpi`, `gold.sales_per_plan`, `gold.failed_payment_user`, `gold.data_quality_summary`）を Databricks SQL Serverless Warehouse 経由で読み取り、REST API として公開する FastAPI バックエンドを `serving_layer/app/backend/` に実装してください。

## 要件

1. `db.py`
   - `databricks-sql-connector` を使い、環境変数 `DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` / `DATABRICKS_TOKEN`（ローカル開発時）または Databricks Apps が注入する認証情報からコネクションを作る。
   - `run_query(sql: str, params: dict | None = None) -> list[dict]` を提供し、SQLインジェクションを避けるためプレースホルダを使うこと。
   - 接続はリクエスト毎に使い捨てず、コネクションプール（もしくは軽量なシングルトン）で使い回すこと。
2. `routers/kpi.py` — `GET /api/v1/daily-kpi?start=YYYY-MM-DD&end=YYYY-MM-DD`
   - `daily_kpi` を日付範囲で取得。デフォルトは直近30日。
   - `free_to_paid_rate` が NULL の場合は 0 として返すのではなく、`null` のまま返す（欠損を隠さない）。
3. `routers/sales.py` — `GET /api/v1/sales-per-plan?months=N`
   - `sales_per_plan` を `sales_month` 降順で取得し、直近N ヶ月（デフォルト12）を返す。
   - プランごとの `total_revenue` の前月比（MoM）をAPI側で計算して付加する（フロントで再計算しなくて済むように）。
4. `routers/failed_payments.py` — `GET /api/v1/failed-payment-users?risk=all|high|low&sort=...`
   - `failed_payment_user` を取得。`churn_risk_flag=true` を「high」として絞り込めるようにする。
   - CS/営業が優先順位をつけやすいよう、`total_failed_count` 降順をデフォルトソートにする。
5. `routers/data_quality.py` — `GET /api/v1/data-quality-summary?days=N`
   - `data_quality_summary` を `run_date` 降順、直近N日（デフォルト14）で取得。
6. `models.py` に各レスポンスの Pydantic モデルを定義し、Gold テーブル定義のカラム名・型と完全に一致させること（勝手にカラムを追加/改名しない）。
7. `main.py`
   - 上記4ルーターを `/api/v1` prefix でマウント。
   - `/healthz` エンドポイントを追加（Databricks Apps のヘルスチェック用）。
   - 本番ビルドではフロントエンドの `dist/` を静的ファイルとして配信する（Phase 3 で接続）。

## 確認事項

- 実装後、ダミーの `run_query` をモックした単体テスト、または実際の Warehouse に接続できる環境であれば `curl` で疎通確認をしてください。
- Gold テーブルのカラムに存在しない項目をAPIレスポンスに含めていないか、CLAUDE.md のテーブル定義と突き合わせて確認してください。
