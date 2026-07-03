# Gold Layer Serving Dashboard（Step 5: Serving Layer）

Gold layer の4テーブル（`daily_kpi` / `sales_per_plan` / `failed_payment_user` / `data_quality_summary`）を、業務利用者（経営層・事業企画・CS／営業・データエンジニアリング）に向けて提供する Serving layer です。**Databricks Free Edition 上の Databricks Apps** としてデプロイすることを前提に、TypeScript + React のフロントエンドと Python (FastAPI) のバックエンドで構成しています。

このディレクトリは Step 5（Serving layer）専用の成果物です。Bronze/Silver/Gold（Step 1〜4）のコードには含まれません。

## なぜこの構成か

| 論点 | 選択 | 理由 |
|---|---|---|
| クエリエンジン | Databricks SQL Serverless Warehouse | Gold の4テーブルはいずれも集計済みで行数が小さく、BI的な読み取りが中心。サーバーレスSQLウェアハウスは起動が速く Free Edition の無料枠と相性が良い。OLTP的な更新は発生しないため Lakebase は不要と判断。 |
| アプリホスティング | Databricks Apps | フロントエンド（React）とバックエンド（FastAPI）を1つのマネージドWebアプリとしてホストでき、Unity Catalog への認証をアプリのサービスプリンシパル経由で完結できる。 |
| フロントエンド | TypeScript + React（Vite） | Streamlit を使わない指定のため。4つのビジネス目的に対応する4画面のSPAとして実装。 |
| バックエンド | Python (FastAPI) | Databricks Apps がネイティブにサポート。`databricks-sql-connector` で Gold スキーマへの読み取り専用アクセスを行う。 |

## ビジネス目的とのマッピング

| 画面 | 対応する Gold テーブル | 利用者 | 解決する意思決定 |
|---|---|---|---|
| 経営KPIダッシュボード | `daily_kpi` | 経営層 | 売上・DAU・新規登録・解約の日次トレンドから事業の調子を素早く把握する |
| プラン別売上 | `sales_per_plan` | 事業企画・プロダクト | 決済失敗率と売上推移から収益が停滞しているプランを特定する |
| 要フォローアップ顧客 | `failed_payment_user` | CS・営業 | 解約リスクの高い決済失敗ユーザーを優先順位付けしてフォローする |
| データ品質サマリー | `data_quality_summary` | データエンジニアリング | Bronze/Silver で検出された品質課題を日次でモニタリングする |

## ディレクトリ構成

```
serving_layer/
  CLAUDE.md              … このプロジェクトでAIアシスタントが従う方針
  README.md              … 本ファイル
  prompts/                … フェーズ毎にAIへ投げるプロンプト（phase1〜phase4）
  docs/screenshots/       … 動作確認時のスクリーンショット
  app/
    app.yaml              … Databricks Apps 設定
    requirements.txt
    backend/               … FastAPI (本番エントリポイントは main.py)
      main.py
      config.py
      db.py
      models.py
      mock_server.py       … ローカル動作確認用（実DB接続なしでも起動可能）
      routers/
    frontend/               … React + TypeScript (Vite)
      src/
        pages/               … 4つのビジネス目的に対応する4画面
        components/
        theme/               … カラートークン
        api/
  scripts/
    deploy.sh              … Databricks Apps デプロイ手順（参考スクリプト）
```

## ローカルでの動作確認

実際の Databricks ワークスペースに接続できない環境（このコーディング演習環境を含む）でも、UIの見た目とAPI契約を確認できるよう `backend/mock_server.py` を用意しています。

```bash
# 1. モックAPIサーバーを起動 (Gold テーブル定義に沿ったダミーデータを返す)
cd app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.mock_server:app --port 8000

# 2. 別ターミナルでフロントエンドを起動 (vite.config.ts が /api を :8000 にプロキシする)
cd app/frontend
npm install
npm run dev
```

`npm run build` で TypeScript の型検査とプロダクションビルドが通ることを確認済みです。4画面（経営KPI／プラン別売上／要フォローアップ顧客／データ品質）をブラウザで開き、レイアウト崩れがないことを Playwright のスクリーンショットで確認しています（`docs/screenshots/` 参照）。

実際の Gold テーブルに接続する場合は、以下の環境変数を設定して `backend.main:app` を起動してください。認証は `databricks.sdk.WorkspaceClient` のデフォルト認証（Unified Authentication）に任せているため、`databricks auth login` 済みのプロファイルがあれば追加の環境変数なしで動作します。

```bash
export DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
export DATABRICKS_CATALOG=workspace
export DATABRICKS_GOLD_SCHEMA=gold
# databricks auth login 済みでなければ、PAT ベースの認証情報も指定する
# export DATABRICKS_HOST=<workspace-hostname>
# export DATABRICKS_TOKEN=<personal-access-token>
uvicorn backend.main:app --port 8000
```

> **Databricks Apps 実行時の注意**: Databricks Apps は `DATABRICKS_HOST` とアプリのサービスプリンシパル用OAuth資格情報を自動注入するが、SQL Warehouse のホスト名・HTTP Path 自体は注入しない。そのため `backend/db.py` では `WorkspaceClient().warehouses.get(warehouse_id)` を使って接続先を都度解決している。`DATABRICKS_WAREHOUSE_ID` は `app.yaml` に**直接値として**書く（`resources:` ブロックによるリソースバインディングは、UI側で明示的に紐付けないと環境変数が注入されず `KeyError` で起動に失敗することを実機で確認したため採用していない）。

## Databricks Apps へのデプロイ

`scripts/deploy.sh` に手順をまとめています（このリポジトリ環境には Databricks ワークスペースへの認証情報がないため、実行はワークスペースにアクセスできる端末で行ってください）。

1. `npm run build` でフロントエンドをビルド（`backend/main.py` が `frontend/dist` を静的配信する）
2. `databricks apps list` で既存アプリ数を確認
   - **Free Edition の上限に達している場合**: 作成日時が最も古いアプリを特定し、**必ずユーザーに削除の確認を取ってから** `databricks apps delete` する（無断で他人のアプリを削除しない）
3. `databricks apps create gold-serving-layer`（初回のみ）
4. `app.yaml` の `DATABRICKS_WAREHOUSE_ID` を実際のSQL Warehouse IDに書き換える
5. `databricks sync app /Workspace/Users/<user>/gold-serving-layer`
6. `databricks apps deploy gold-serving-layer --source-code-path /Workspace/Users/<user>/gold-serving-layer`
7. **権限付与（この2つを忘れるとアプリはクラッシュ、またはクエリが失敗する）**
   - SQL Warehouses > 対象のウェアハウス > Permissions で、アプリのサービスプリンシパルに **Can use** を付与する
   - Catalog Explorer > `gold` スキーマ > Permissions で、同サービスプリンシパルに **SELECT** のみを付与する

## UI デザイン

- チャンパー（サイドバー・カード・バッジ）には Google スライドの配色パレットに近い、淡く鮮やかなパステルカラー（`app/frontend/src/theme/colors.ts` の `uiPastel`）を使用しています。
- グラフの系列色は、パステルカラーがコントラスト不足でデータエンコードに不向きなため、アクセシビリティ検証済みの配色（`chartSeries`）を別途使用しています（`dataviz` スキルの検証スクリプトでCVD安全性を確認済み）。
- 解約リスクなどのステータス表示は色だけに依存せず、常にラベルを併記しています。

## 既知の制約・スコープ外事項

- **書き込み機能なし**: Serving layer は読み取り専用です。CS が「対応済みにする」等のワークフローは今回のスコープ外です。
- **`data_quality_summary` のカラム定義**: 本タスクで渡された Gold layer 設計メモには grain（`run_date` × `source_table` × `dq_check_name`）のみが明記され、指標カラムの定義がなかったため、目的（品質課題の日次集計）から `failed_record_count` / `checked_record_count` / `failed_rate` を妥当な指標として推測して実装しています。実際の Gold テーブルのカラム名と異なる場合は `backend/models.py` と `routers/data_quality.py` を実テーブル定義に合わせて調整してください。
- **認証**: エンドユーザー単位の認可は行わず、アプリのサービスプリンシパルに対する Unity Catalog 権限（`gold` スキーマの `SELECT` のみ）で制御する前提です。個人ごとのアクセス制御が必要な場合は別途設計が必要です。
- **実ワークスペースでの動作確認**: この開発環境には Databricks ワークスペースへの接続情報がないため、実際の SQL Warehouse に対するクエリ疎通確認は行えていません。デプロイ後、`/healthz` と各 `/api/v1/*` エンドポイントの疎通を確認してください。
