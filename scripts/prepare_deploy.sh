#!/usr/bin/env bash
# Databricks Appsへデプロイする前に、Reactのproduction buildとPythonテストを
# 一括実行するスクリプト。
#
# デプロイ前ビルド方式：Databricks Apps起動時にNode.js/npmは実行しない。
# このスクリプトをローカルまたはCI環境で実行し、生成された frontend/dist を
# デプロイ対象フォルダーへ含めること。
#
# いずれかの手順が失敗した場合は直ちに停止し、非0の終了コードを返す。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
DIST_DIR="${FRONTEND_DIR}/dist"
DIST_INDEX="${DIST_DIR}/index.html"

log() {
  echo "[prepare_deploy] $*"
}

fail() {
  echo "[prepare_deploy] エラー: $*" >&2
  exit 1
}

log "1/7 必要なコマンドを確認します"
command -v node >/dev/null 2>&1 || fail "node コマンドが見つかりません。Node.jsをインストールしてください。"
command -v npm >/dev/null 2>&1 || fail "npm コマンドが見つかりません。Node.jsをインストールしてください。"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 / python コマンドが見つかりません。"

"$PYTHON_BIN" -c "import pytest" >/dev/null 2>&1 || \
  fail "pytest がインストールされていません。'pip install -r requirements.txt' を実行してください。"

log "2/7 フロントエンド依存をインストールします (npm ci)"
(cd "$FRONTEND_DIR" && npm ci) || fail "npm ci に失敗しました。"

log "3/7 TypeScript型チェックを実行します"
(cd "$FRONTEND_DIR" && npm run typecheck) || fail "TypeScript型チェックに失敗しました。"

log "4/7 Production Buildを実行します"
(cd "$FRONTEND_DIR" && npm run build) || fail "フロントエンドのビルドに失敗しました。"

log "5/7 ビルド成果物を確認します"
if [ ! -f "$DIST_INDEX" ]; then
  fail "${DIST_INDEX} が見つかりません。ビルドが正しく完了していません。"
fi
log "確認OK: ${DIST_INDEX}"

log "6/7 Pythonの主要テストを実行します"
(cd "$ROOT_DIR" && "$PYTHON_BIN" -m pytest backend/tests -v) || fail "Pythonテストに失敗しました。"

log "7/7 デプロイ対象のファイル構成を確認します"
echo "--------------------------------------------------"
echo "以下がDatabricks Appsへ配置するソースフォルダーに含まれることを確認してください:"
echo "  app.yaml"
echo "  requirements.txt"
echo "  backend/"
echo "  frontend/dist/  (ビルド済み。Git管理外のため個別に同期が必要)"
echo "--------------------------------------------------"
(
  cd "$ROOT_DIR" && \
  find . -maxdepth 2 \( -name node_modules -o -name ".venv" -o -name ".git" \) -prune -o \
    -mindepth 1 -maxdepth 2 -print | sort
)
echo "--------------------------------------------------"

log "デプロイ前準備がすべて成功しました。上記フォルダー構成をDatabricksワークスペースへ同期してください。"
exit 0
