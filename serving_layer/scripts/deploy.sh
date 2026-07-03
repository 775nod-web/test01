#!/usr/bin/env bash
# Databricks Apps へのデプロイ手順（参考スクリプト）。
#
# このスクリプトは手順のドキュメントを兼ねており、実行前に必ず内容を確認する
# こと。Databricks CLI の認証 (databricks auth login 等) が済んでいる前提。
# このリポジトリ環境からは実 Databricks ワークスペースへの認証情報を持たない
# ため、実際のデプロイは対象ワークスペースにアクセスできる端末で行うこと。

set -euo pipefail

APP_NAME="${APP_NAME:-gold-serving-layer}"
WORKSPACE_USER="${WORKSPACE_USER:?WORKSPACE_USER (例: user@example.com) を指定してください}"
SOURCE_PATH="/Workspace/Users/${WORKSPACE_USER}/${APP_NAME}"

echo "== 1. フロントエンドをビルド =="
(cd "$(dirname "$0")/../app/frontend" && npm install && npm run build)

echo "== 2. 既存アプリ数を確認 (Free Edition の上限に達している場合の対応) =="
echo "  以下を手動確認し、上限エラーが出た場合のみ次のステップに進むこと。"
echo "  databricks apps list"
echo "  # 上限に達していた場合: 作成日時が最も古いアプリを特定し、"
echo "  # 必ずユーザーに確認を取ってから削除する（無断で他人のアプリを消さない）。"
echo "  # databricks apps delete <oldest-app-name>"

echo "== 3. アプリの作成（初回のみ） =="
echo "  databricks apps create \"${APP_NAME}\""

echo "== 4. ソースコードをワークスペースに同期 =="
echo "  databricks sync \"$(dirname "$0")/../app\" \"${SOURCE_PATH}\""

echo "== 5. デプロイ =="
echo "  databricks apps deploy \"${APP_NAME}\" --source-code-path \"${SOURCE_PATH}\""

echo "== 完了後の確認 =="
echo "  databricks apps get \"${APP_NAME}\""
echo "  # アプリURLにアクセスし、/healthz が {\"status\": \"ok\"} を返すことを確認する"
