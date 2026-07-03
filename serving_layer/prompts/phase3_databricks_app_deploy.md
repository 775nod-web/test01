# Phase 3: Databricks Apps デプロイ プロンプト

Phase 1（backend）・Phase 2（frontend）の成果物を前提に、Databricks Free Edition 上の **Databricks Apps** にデプロイするための設定を整えてください。ローカルにアプリを作って終わりにしないこと。

## ゴール

1. `serving_layer/app/app.yaml` を作成し、Databricks Apps がアプリを起動できるようにする。
   - `command`: `uvicorn backend.main:app --host 0.0.0.0 --port $DATABRICKS_APP_PORT` 相当。
   - `env`: SQL Warehouse の HTTP Path などをリソース参照で渡す。
   - `resources`: 利用する SQL Warehouse（Serverless）をリソースとして宣言し、`gold` スキーマへの `SELECT` 権限のみを付与する前提を明記する。
2. `serving_layer/app/requirements.txt` に `fastapi`, `uvicorn`, `databricks-sql-connector`, `databricks-sdk` 等、バックエンドに必要な依存を列挙する。
3. フロントエンドのビルド成果物（`frontend/dist`）を `backend/main.py` から `StaticFiles` で配信するようにし、単一の Databricks App として動作する構成にする。
4. `serving_layer/scripts/deploy.sh` に、以下の手順を **コメント付きで** 記述する（実行はユーザー確認の上で行うこと。無許可で実行しない）:
   - `npm run build`（frontend）
   - `databricks apps create <app-name>`（初回のみ）
   - `databricks sync serving_layer/app /Workspace/Users/<user>/serving_layer_app`
   - `databricks apps deploy <app-name> --source-code-path /Workspace/Users/<user>/serving_layer_app`
5. **Databricks Apps の上限に達している場合の対応** をスクリプトのコメントとして明記する:
   - `databricks apps list` で既存アプリの一覧と作成日時を確認し、最も古いアプリを特定する。
   - 削除前に必ずユーザーに確認を取ってから `databricks apps delete <oldest-app-name>` を実行すること（無断で他人の古いアプリを消さない）。
6. `serving_layer/README.md` にセットアップからデプロイまでの手順をまとめる（Phase 4 で仕上げる想定）。

## 確認事項

- `app.yaml` の構文が Databricks Apps の仕様に沿っているか（`command` / `env` / `resources` のキー）を再確認する。
- デプロイスクリプトはあくまで手順書であり、この環境から直接 Databricks ワークスペースへ本番デプロイを実行しない（実行環境に Databricks CLI 認証がない場合は特に）。
