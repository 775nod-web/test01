"""
Shared catalog/schema resolution for Databricks notebooks in this project.

This workspace's capabilities (Unity Catalog vs. Hive metastore) could not
be verified in advance — the coding session that built this had no network
path to any Databricks workspace. Every notebook that reads or writes
tables calls resolve_schema_prefix() so they agree on where tables live,
instead of each notebook guessing independently.
"""

from __future__ import annotations


def resolve_schema_prefix(spark, catalog: str, schema_name: str) -> str:
    """Return the resolved '<catalog>.<schema>' or Hive-fallback
    '<catalog>_<schema>' prefix for a given logical schema (e.g. "bronze",
    "silver", "gold"), creating the catalog/schema/database as needed.
    Prints which mode was used so it is visible in notebook output rather
    than assumed."""
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
        spark.sql(f"USE CATALOG {catalog}")
        prefix = f"{catalog}.{schema_name}"
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {prefix}")
        print(f"Unity Catalog available. Using {prefix}.<table>")
        return prefix
    except Exception as exc:
        prefix = f"{catalog}_{schema_name}"
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {prefix}")
        print(
            f"Unity Catalog not available or not permitted here "
            f"({type(exc).__name__}: {exc}). Falling back to Hive metastore "
            f"database '{prefix}'. Using {prefix}.<table>"
        )
        return prefix
