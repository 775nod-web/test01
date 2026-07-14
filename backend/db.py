"""
Query engine abstraction. Loads sql/queries/*.sql (Phase 5 assets) and
executes them against either:

  - Databricks SQL (production — Databricks Apps runtime), via
    databricks-sql-connector, authenticating through the Databricks SDK's
    default credential chain (no static tokens in source or config).
  - A local DuckDB session reading backend/local_fixtures/*.parquet (dev
    only — used automatically when Databricks connection env vars are not
    present, e.g. running `uvicorn backend.main:app` on a laptop).

Both engines accept the same canonical query files, written with
Databricks/Spark-native named parameters (`:param_name`) and `{gold}` /
`{silver}` schema placeholders. Never build SQL by string-concatenating
user input — all endpoint parameters flow through the `params` dict here
and are bound by the driver, not interpolated into the SQL text.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_QUERIES_DIR = REPO_ROOT / "sql" / "queries"
LOCAL_FIXTURES_DIR = Path(__file__).resolve().parent / "local_fixtures"


class QueryError(RuntimeError):
    """Raised when a query file is missing or execution fails."""


@lru_cache(maxsize=None)
def _load_query_text(name: str) -> str:
    path = SQL_QUERIES_DIR / name
    if not path.exists():
        raise QueryError(f"Unknown query asset: {name}")
    return path.read_text()


class QueryEngine:
    def run(self, name: str, **params: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def health_check(self) -> None:
        raise NotImplementedError


class DatabricksQueryEngine(QueryEngine):
    """Production engine. Resolves whether the target catalog uses Unity
    Catalog or a Hive metastore database once at startup (mirroring
    notebooks/lib/catalog_utils.py), then reuses that resolution for every
    request."""

    def __init__(self, catalog: str, http_path: str, server_hostname: str):
        from databricks import sql as databricks_sql
        from databricks.sdk.core import Config

        self._databricks_sql = databricks_sql
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._sdk_config = Config()
        self._catalog = catalog
        self._lock = threading.Lock()
        self._gold_prefix: str | None = None
        self._silver_prefix: str | None = None

    def _connect(self):
        return self._databricks_sql.connect(
            server_hostname=self._server_hostname,
            http_path=self._http_path,
            credentials_provider=lambda: self._sdk_config.authenticate,
        )

    def _resolve_prefixes(self) -> None:
        if self._gold_prefix is not None:
            return
        with self._lock:
            if self._gold_prefix is not None:
                return
            with self._connect() as conn, conn.cursor() as cursor:
                try:
                    cursor.execute(f"SELECT 1 FROM {self._catalog}.gold.executive_kpis LIMIT 1")
                    self._gold_prefix = f"{self._catalog}.gold"
                    self._silver_prefix = f"{self._catalog}.silver"
                except Exception:
                    self._gold_prefix = f"{self._catalog}_gold"
                    self._silver_prefix = f"{self._catalog}_silver"
            logger.info(
                "Resolved Databricks schema prefixes: gold=%s silver=%s",
                self._gold_prefix,
                self._silver_prefix,
            )

    def run(self, name: str, **params: Any) -> list[dict[str, Any]]:
        self._resolve_prefixes()
        sql_text = _load_query_text(name)
        sql_text = sql_text.replace("{gold}", self._gold_prefix).replace("{silver}", self._silver_prefix)
        sql_text = sql_text.rstrip().rstrip(";")
        try:
            with self._connect() as conn, conn.cursor() as cursor:
                cursor.execute(sql_text, parameters=params)
                columns = [c[0] for c in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            raise QueryError(f"Databricks query '{name}' failed: {exc}") from exc

    def health_check(self) -> None:
        self._resolve_prefixes()
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchall()


class LocalDuckDBQueryEngine(QueryEngine):
    """Dev-only fallback so the app runs and can be demoed without a
    Databricks connection. Reads backend/local_fixtures/*.parquet (see
    scripts/generate_local_fixtures.py). Never used when Databricks
    connection env vars are configured."""

    _NAMED_PARAM_RE = re.compile(r":(\w+)\b")

    _FIXTURE_MAP = {
        "gold.customer_360": "gold_customer_360.parquet",
        "gold.retention_action_list": "gold_retention_action_list.parquet",
        "gold.executive_kpis": "gold_executive_kpis.parquet",
        "silver.account_transactions": "silver_account_transactions.parquet",
        "silver.card_usage": "silver_card_usage.parquet",
        "silver.app_activity": "silver_app_activity.parquet",
        "silver.product_holdings": "silver_product_holdings.parquet",
        "silver.contact_history": "silver_contact_history.parquet",
    }

    def __init__(self):
        import duckdb

        self._lock = threading.Lock()
        self._con = duckdb.connect(database=":memory:")
        self._con.execute("CREATE SCHEMA IF NOT EXISTS gold")
        self._con.execute("CREATE SCHEMA IF NOT EXISTS silver")

        for view_name, filename in self._FIXTURE_MAP.items():
            file_path = LOCAL_FIXTURES_DIR / filename
            if not file_path.exists():
                raise QueryError(
                    f"Missing local fixture {file_path}. Run "
                    f"`pip install -r requirements-dev.txt && "
                    f"python scripts/generate_local_fixtures.py` first."
                )
            self._con.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{file_path.as_posix()}')"
            )
        logger.warning(
            "Using LOCAL DuckDB fixture data (backend/local_fixtures/*.parquet) — "
            "this is a dev-only fallback, not the Databricks deployment path."
        )

    def run(self, name: str, **params: Any) -> list[dict[str, Any]]:
        sql_text = _load_query_text(name)
        sql_text = sql_text.replace("{gold}", "gold").replace("{silver}", "silver")
        sql_text = sql_text.rstrip().rstrip(";")
        duckdb_sql = self._NAMED_PARAM_RE.sub(lambda m: f"${m.group(1)}", sql_text)
        try:
            with self._lock:
                result = self._con.execute(duckdb_sql, params)
                columns = [c[0] for c in result.description]
                return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as exc:
            raise QueryError(f"Local query '{name}' failed: {exc}") from exc

    def health_check(self) -> None:
        with self._lock:
            self._con.execute("SELECT 1").fetchall()


@lru_cache(maxsize=1)
def get_query_engine() -> QueryEngine:
    server_hostname = os.environ.get("DATABRICKS_SERVER_HOSTNAME")
    http_path = os.environ.get("DATABRICKS_HTTP_PATH")
    catalog = os.environ.get("UC_CATALOG", "bank_demo")

    if server_hostname and http_path:
        logger.info("Using Databricks SQL engine (catalog=%s)", catalog)
        return DatabricksQueryEngine(catalog=catalog, http_path=http_path, server_hostname=server_hostname)

    logger.warning(
        "DATABRICKS_SERVER_HOSTNAME/DATABRICKS_HTTP_PATH not set — falling back "
        "to local DuckDB fixture data. This is expected in local development, "
        "not in a deployed Databricks App (attach a SQL warehouse resource)."
    )
    return LocalDuckDBQueryEngine()
