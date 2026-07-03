"""Databricks SQL Serverless Warehouse への読み取り専用アクセス。

Gold layer (`<catalog>.<schema>.*`) に対する SELECT のみを行う。
コネクションはプロセス内で使い回し、リクエスト毎に張り直さない。
"""

import threading
from typing import Any

from databricks import sql as dbsql

from .config import get_settings

_settings = get_settings()
_local = threading.local()


def _connect():
    kwargs: dict[str, Any] = {
        "server_hostname": _settings.server_hostname,
        "http_path": _settings.http_path,
    }
    if _settings.access_token:
        # ローカル開発 (Personal Access Token)
        kwargs["access_token"] = _settings.access_token
    else:
        # Databricks Apps 実行時: アプリのサービスプリンシパルによる OAuth (M2M)
        kwargs["auth_type"] = "databricks-oauth"
        kwargs["client_id"] = _settings.client_id
        kwargs["client_secret"] = _settings.client_secret
    return dbsql.connect(**kwargs)


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
