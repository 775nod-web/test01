# CLAUDE.md — Serving Layer (Step 5)

このファイルは、`serving_layer/` 配下で Claude Code（または他のAIコーディングアシスタント）が作業する際の方針をまとめたものです。Step 5「Serving layer」の実装専用であり、Bronze/Silver/Gold（Step 1〜4）のコードには一切手を加えないでください。

## スコープ

- 対象: Gold layer の4テーブル（`gold.daily_kpi` / `gold.sales_per_plan` / `gold.failed_payment_user` / `gold.data_quality_summary`）を読み取り専用で提供する Serving layer（API + UI）
- 非対象: サンプルデータ生成、Bronze/Silver/Gold の変換ロジック、データ品質チェックの実装そのもの（`data_quality_summary` は Gold 側で既に集計済みという前提で「読む」だけ）
- 成果物は最終的に **Databricks Apps** 上にデプロイする。ローカル実行はあくまで開発時の動作確認用。

## ビジネス目的（Gold テーブル定義の Purpose 列に準拠）

| Gold Table | 想定利用者 | 目的 | Serving layer での提供形態 |
|---|---|---|---|
| `daily_kpi` | 経営層 | 日次の売上・DAU・新規登録・有料転換・解約を一覧で把握する | Executive KPI ダッシュボード（トレンドグラフ＋当日サマリーカード） |
| `sales_per_plan` | 事業企画・プロダクト | どのプランで収益が停滞しているかを特定する | プラン別売上・失敗率の比較ビュー（月次推移＋プラン間比較） |
| `failed_payment_user` | CS・営業 | 決済失敗ユーザーへのフォローアップの優先順位付け | 解約リスクでソート可能なアクションリスト（フィルタ・検索付き） |
| `data_quality_summary` | データエンジニアリング | Bronze/Silver で検出された品質課題を日次モニタリングする | DQチェック結果のヒートマップ／一覧 |

新しい画面や指標を追加する際は、必ず「どの利用者の、どの意思決定を助けるか」をこの表に沿って明確にしてから実装すること。

## アーキテクチャ方針

```
[Unity Catalog: gold.*]
        │  (SELECT のみ、書き込みなし)
        ▼
[Databricks SQL Serverless Warehouse]
        │  databricks-sql-connector (Statement Execution)
        ▼
[FastAPI backend  (Python)]  … Databricks Apps 上で uvicorn 起動
        │  REST API (/api/v1/*)
        ▼
[React + TypeScript frontend (Vite build)] … backend が静的配信
```

- **なぜ Databricks SQL Serverless Warehouse か**: 4つの Gold テーブルはいずれも集計済みで行数が小さい（daily_kpiは日次1行、sales_per_planは月次×プラン数行など）。BIクエリ主体の読み取りに対してサーバーレスSQLウェアハウスは起動が速く、Free Edition の無料枠と相性が良い。OLTP的な更新は発生しないため Lakebase（Postgres）は不要と判断。
- **なぜ Databricks Apps か**: フロントエンド（React）とバックエンド（FastAPI）を1つのマネージドWebアプリとしてホストでき、Unity Catalog への認証をアプリのサービスプリンシパル経由で完結できるため、認証まわりの実装コストが最小になる。
- **認証**: Databricks Apps の `app.yaml` で SQL Warehouse をリソースとして宣言し、アプリ実行時に注入される `DATABRICKS_HOST` / `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`（またはOAuthトークン）を `databricks-sql-connector` に渡す。個々のエンドユーザー認証は行わず、アプリの実行権限に対して Unity Catalog 側で `gold` スキーマへの `SELECT` のみを許可する。
- **書き込みは行わない**: Serving layer は読み取り専用。CSアクションの「対応済みにする」等のワークフローは将来の別チケットとし、今回は実装しない（=禁止されている他ステップの範囲を広げない）。

## ディレクトリ構成

```
serving_layer/
  CLAUDE.md              … このファイル
  README.md              … セットアップ・デプロイ手順
  prompts/                … フェーズ毎にAIへ投げるプロンプト
    phase1_backend_api.md
    phase2_frontend_ui.md
    phase3_databricks_app_deploy.md
    phase4_verification.md
  app/
    app.yaml              … Databricks Apps 設定
    requirements.txt
    backend/
      main.py             … FastAPI エントリポイント（静的ファイル配信込み）
      config.py           … 環境変数・Warehouse接続設定
      db.py               … databricks-sql-connector ラッパー
      models.py           … Pydantic レスポンススキーマ
      routers/
        kpi.py             … /api/v1/daily-kpi
        sales.py            … /api/v1/sales-per-plan
        failed_payments.py  … /api/v1/failed-payment-users
        data_quality.py     … /api/v1/data-quality-summary
    frontend/
      src/
        pages/             … 4つのビジネス目的に対応する4画面
        components/        … KPIカード、テーブル、チャート等の共通部品
        theme/             … カラーパレット・トークン定義
        api/               … バックエンド呼び出しクライアント
  scripts/
    deploy.sh              … databricks apps deploy 用スクリプト
```

## コーディング規約

- バックエンド: Python 3.11+ / FastAPI / Pydantic v2。SQLは `routers/` 内で直接文字列を組み立てず、`db.py` の `run_query(sql, params)` 経由でパラメータ化する（インジェクション対策）。
- フロントエンド: TypeScript + React（Vite）。**Streamlit は使用しない**。状態管理はライブラリ追加を避け、React Query 相当のシンプルなカスタムフックで十分。
- UI カラー: `frontend/src/theme/colors.ts` に定義した Google スライド風の淡く鮮やかなパレットを使う。グラフの系列色は視認性検証済みの配色（`references/palette.md` 準拠）を使用し、UIチャンパー（カード背景・バッジ・サイドバー）にパステル配色を使う住み分けとする。
- コメントは「なぜ」を説明する場合のみ最小限。自明なコードにコメントを書かない。
- 新しいテーブルやカラムを Serving layer で参照する場合は、必ず Gold layer の設計メモ（本タスクの `sales_per_plan` 等のテーブル定義）に存在するカラム名と型に一致させること。存在しないカラムを推測で使わない。

## やってはいけないこと（Step 5 スコープ外）

- Bronze/Silver/Gold のノートブックやテーブル定義の変更
- 新しい Gold テーブルの追加や既存 Gold テーブルのスキーマ変更
- サンプルデータ生成スクリプトの変更
- Serving layer からの書き込み・更新処理の実装
