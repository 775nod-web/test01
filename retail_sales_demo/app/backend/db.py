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
        on_wait_timeout="CONTINUE",
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

    columns = [col.name for col in response.manifest.schema.columns or []]
    rows = (response.result.data_array if response.result else None) or []
    return [dict(zip(columns, row)) for row in rows]
