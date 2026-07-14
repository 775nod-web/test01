"""
App-wide settings, read from environment variables only — no secrets or
workspace-specific IDs are hardcoded here. Databricks connection details
(DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH) are read directly by
backend/db.py so the SQL-warehouse resource attached in Databricks Apps
"just works" without extra wiring.
"""

from __future__ import annotations

import os


class Settings:
    app_port: int = int(os.environ.get("DATABRICKS_APP_PORT", "8000"))
    uc_catalog: str = os.environ.get("UC_CATALOG", "bank_demo")
    app_title: str = "Bank Customer Retention Demo API"
    app_version: str = "0.1.0"


settings = Settings()
