"""起動設定の解決ロジック。

Databricks Apps / ローカル開発の両方で、ホスト・ポート・データモードを
矛盾なく解決するための独立関数を提供する。単体テストで優先順位を検証できるように
副作用を持たない純粋関数として実装する。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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


# 生成方式（Layer 3）。内部値とUI表示名はCLAUDE.md/DEMO_SPEC.mdの定義に従う。
GENERATION_MODE_LLM = "llm"
GENERATION_MODE_PRE_GENERATED = "pre_generated"
GENERATION_MODE_RULE_BASED = "rule_based"

GENERATION_MODE_LABEL = {
    GENERATION_MODE_LLM: "LLM生成",
    GENERATION_MODE_PRE_GENERATED: "事前生成済みLLM回答",
    GENERATION_MODE_RULE_BASED: "デモ用ルールベース生成",
}

DEFAULT_LLM_TIMEOUT_SECONDS = 8.0
DEFAULT_LLM_MAX_RETRIES = 1


@dataclass(frozen=True)
class LLMConfig:
    endpoint_url: str
    api_key: str
    model: str | None
    timeout_seconds: float
    max_retries: int


def resolve_llm_config(env: "os._Environ[str] | dict[str, str] | None" = None) -> LLMConfig | None:
    """LLM接続設定を環境変数から解決する。

    エンドポイントURLと認証情報が両方とも設定されている場合のみ設定済みとみなし、
    LLMConfigを返す。未設定の場合はNoneを返し、呼び出し側は次の生成方式へ進む。
    接続情報・モデル名・認証情報はコードへ直接記載せず、すべて環境変数から取得する。
    """
    source = env if env is not None else os.environ
    endpoint_url = source.get("LLM_ENDPOINT_URL") or ""
    api_key = source.get("LLM_API_KEY") or ""
    if not endpoint_url or not api_key:
        return None

    timeout_raw = source.get("LLM_TIMEOUT_SECONDS")
    try:
        timeout_seconds = float(timeout_raw) if timeout_raw else DEFAULT_LLM_TIMEOUT_SECONDS
    except ValueError:
        timeout_seconds = DEFAULT_LLM_TIMEOUT_SECONDS

    retries_raw = source.get("LLM_MAX_RETRIES")
    try:
        max_retries = int(retries_raw) if retries_raw else DEFAULT_LLM_MAX_RETRIES
    except ValueError:
        max_retries = DEFAULT_LLM_MAX_RETRIES

    return LLMConfig(
        endpoint_url=endpoint_url,
        api_key=api_key,
        model=source.get("LLM_MODEL") or None,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
