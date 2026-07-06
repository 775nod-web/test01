"""Serverless SQL Warehouse へのクエリ実行ラッパー。

Databricks Apps上で実行される前提のため、認証はDatabricks SDKの
デフォルト資格情報チェーン（Appsのサービスプリンシパル/ホスト情報が自動的に
環境変数として注入される）に委ねる。ローカルで動作確認する場合は
`databricks auth login` 等でCLIプロファイルを設定しておくこと。

未接続環境で作成したコードのため、SDKのレスポンス構造（manifest/result等の
フィールド名）は実際のワークスペースに接続した際に必ず動作確認すること。
"""
import time
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState

from .config import WAREHOUSE_ID

_client: WorkspaceClient | None = None


def get_client() -> WorkspaceClient:
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def _build_parameters(params: dict[str, Any] | None) -> list[StatementParameterListItem]:
    if not params:
        return []
    return [
        StatementParameterListItem(name=key, value=str(value))
        for key, value in params.items()
        if value is not None
    ]


def run_query(statement: str, params: dict[str, Any] | None = None, timeout_s: int = 30) -> list[dict]:
    """SQLを実行し、結果を dict のリストとして返す。

    statement内のパラメータは Databricks SQL の名前付きパラメータ構文
    （例: :store_id）で記述すること。
    """
    client = get_client()
    response = client.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=statement,
        parameters=_build_parameters(params),
        wait_timeout="10s",
    )

    waited = 0
    while response.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if waited >= timeout_s:
            raise TimeoutError(f"Query timed out after {timeout_s}s: {statement[:120]}")
        time.sleep(1)
        waited += 1
        response = client.statement_execution.get_statement(response.statement_id)

    if response.status.state != StatementState.SUCCEEDED:
        error = response.status.error
        raise RuntimeError(f"Query failed ({response.status.state}): {error}")

    if response.manifest is None or response.manifest.schema is None:
        return []

    columns = response.manifest.schema.columns or []
    names = [col.name for col in columns]
    type_names = [str(getattr(col, "type_name", "") or "") for col in columns]
    rows = (response.result.data_array if response.result else None) or []
    return [
        {name: _cast_value(value, type_name) for name, value, type_name in zip(names, row, type_names)}
        for row in rows
    ]


def _cast_value(value: str | None, type_name: str) -> Any:
    """Statement Execution APIは値を常に文字列で返すため、manifestの型情報を
    見てPythonの型（int/float/bool）に変換する。フロントエンドでの数値計算・
    表示（toLocaleString等）や、バックエンド側の算術演算に必要。
    """
    if value is None:
        return None
    if "INT" in type_name or "LONG" in type_name:
        return int(value)
    if "DOUBLE" in type_name or "FLOAT" in type_name or "DECIMAL" in type_name:
        return float(value)
    if "BOOLEAN" in type_name:
        return value.lower() == "true"
    return value
