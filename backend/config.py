"""起動設定の解決ロジック。

Databricks Apps / ローカル開発の両方で、ホスト・ポート・データモードを
矛盾なく解決するための独立関数を提供する。単体テストで優先順位を検証できるように
副作用を持たない純粋関数として実装する。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

# ポート解決の優先順位（先に見つかったものを採用する）
PORT_ENV_VARS = ("DATABRICKS_APP_PORT", "UVICORN_PORT", "PORT")

# データモード判定に使う Databricks SQL 接続情報
DATABRICKS_SQL_ENV_VARS = (
    "DATABRICKS_SERVER_HOSTNAME",
    "DATABRICKS_HTTP_PATH",
    "DATABRICKS_TOKEN",
)

DATA_MODE_DEMO = "demo"
DATA_MODE_DATABRICKS = "databricks"

# APP_ENV=production の場合のみ本番（Databricks Apps）モードとして扱う。
# 未設定または他の値はすべて development として扱う。
APP_ENV_DEVELOPMENT = "development"
APP_ENV_PRODUCTION = "production"


def resolve_host(env: "os._Environ[str] | dict[str, str] | None" = None) -> str:
    """UVICORN_HOST が設定されていればそれを使い、なければ 0.0.0.0 を返す。"""
    source = env if env is not None else os.environ
    return source.get("UVICORN_HOST") or DEFAULT_HOST


def resolve_port(env: "os._Environ[str] | dict[str, str] | None" = None) -> int:
    """DATABRICKS_APP_PORT → UVICORN_PORT → PORT → 8000 の優先順位でポートを解決する。"""
    source = env if env is not None else os.environ
    for var_name in PORT_ENV_VARS:
        value = source.get(var_name)
        if value:
            return int(value)
    return DEFAULT_PORT


def resolve_data_mode(env: "os._Environ[str] | dict[str, str] | None" = None) -> str:
    """Databricks SQL接続情報が揃っていれば databricks、そうでなければ demo を返す。"""
    source = env if env is not None else os.environ
    if all(source.get(var_name) for var_name in DATABRICKS_SQL_ENV_VARS):
        return DATA_MODE_DATABRICKS
    return DATA_MODE_DEMO


def resolve_app_env(env: "os._Environ[str] | dict[str, str] | None" = None) -> str:
    """APP_ENVが'production'の場合のみproductionを返し、それ以外はdevelopmentを返す。"""
    source = env if env is not None else os.environ
    value = (source.get("APP_ENV") or "").strip().lower()
    if value == APP_ENV_PRODUCTION:
        return APP_ENV_PRODUCTION
    return APP_ENV_DEVELOPMENT


def current_timestamp() -> str:
    """UTCのISO8601形式で現在時刻を返す（データ更新時刻表示用）。"""
    return datetime.now(timezone.utc).isoformat()
