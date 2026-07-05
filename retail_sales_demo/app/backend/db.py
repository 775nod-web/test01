"""SQL Warehouse connection helper.

Uses the Databricks SDK's `Config` for auth so the same code works both
locally (PAT via `DATABRICKS_TOKEN`) and when deployed as a Databricks App
(OAuth M2M via the app's service principal, injected automatically at
runtime) — see https://docs.databricks.com/aws/en/dev-tools/sdk-python/#authentication.
"""
from contextlib import contextmanager
from typing import Any, Iterable, Mapping

from databricks import sql as databricks_sql
from databricks.sdk.core import Config

from . import config


def _http_path(warehouse_id: str) -> str:
    return f"/sql/1.0/warehouses/{warehouse_id}"


@contextmanager
def get_connection():
    cfg = Config()  # picks up DATABRICKS_HOST + token/OAuth from the environment
    connection = databricks_sql.connect(
        server_hostname=cfg.host,
        http_path=_http_path(config.DATABRICKS_WAREHOUSE_ID),
        credentials_provider=lambda: cfg.authenticate,
    )
    try:
        yield connection
    finally:
        connection.close()


def run_query(sql_text: str, params: Mapping[str, Any] | None = None) -> list[dict]:
    """Execute a parameterized SELECT and return rows as a list of dicts."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_text, params or {})
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def execute(sql_text: str, params: Mapping[str, Any] | None = None) -> None:
    """Execute a parameterized INSERT/UPDATE/DDL statement (no result rows)."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_text, params or {})
