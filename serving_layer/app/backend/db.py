"""Databricks SQL Serverless Warehouse への読み取り専用アクセス。

Gold layer (`<catalog>.<schema>.*`) に対する SELECT のみを行う。
コネクションはプロセス内で使い回し、リクエスト毎に張り直さない。

認証は `databricks.sdk.WorkspaceClient` に任せる。Databricks Apps 実行時は
アプリのサービスプリンシパル資格情報（`DATABRICKS_HOST` /
`DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET`）が自動注入されており、
WorkspaceClient がそれを自動検出する。SQL Warehouse のホスト名・HTTP Path
は固定の環境変数としては注入されないため、ウェアハウスID
(`DATABRICKS_WAREHOUSE_ID`) から都度APIで解決する。
"""

import threading
from typing import Any

from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient

from .config import get_settings

_settings = get_settings()
_local = threading.local()
_workspace_client = WorkspaceClient()


def _connect():
    warehouse = _workspace_client.warehouses.get(_settings.warehouse_id)
    return dbsql.connect(
        server_hostname=warehouse.odbc_params.hostname,
        http_path=warehouse.odbc_params.path,
        credentials_provider=lambda: _workspace_client.config.authenticate,
    )


def _get_connection():
    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = _connect()
        _local.connection = conn
    return conn


def qualified_table(table_name: str) -> str:
    """`gold.daily_kpi` のような完全修飾テーブル名を組み立てる。"""
    return f"{_settings.catalog}.{_settings.schema}.{table_name}"


def run_query(sql_text: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """パラメータ化されたクエリを実行し、辞書のリストとして返す。

    databricks-sql-connector は %(name)s 形式のパラメータバインドをサポートする。
    SQL文字列にユーザー入力を直接埋め込まないこと。
    """
    conn = _get_connection()
    with conn.cursor() as cursor:
        cursor.execute(sql_text, params or {})
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]
