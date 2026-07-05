"""Phase 3-C audit logging.

*** FALLBACK IMPLEMENTATION ***
The preferred approach was to read Databricks' own `system.access.audit`
system table. This session has no network access to the workspace, so
whether that table is queryable on this workspace/edition could not be
checked. This module is the documented fallback: a lightweight, app-owned
audit table (DDL: retail_sales_demo/sql/003_app_audit_log.sql) written to
directly by this API. If `system.access.audit` turns out to be available,
prefer it for anything beyond this demo — it captures far more than this
app's own request log (e.g. direct SQL/notebook access to the same tables).
"""
from __future__ import annotations

import logging

from . import queries
from .db import execute

logger = logging.getLogger("audit")


def record_access(user_email: str, endpoint: str, store_id_filter: str | None, status_code: int) -> None:
    """Best-effort audit write — must never fail the actual API request."""
    try:
        sql, params = queries.build_audit_log_insert(user_email, endpoint, store_id_filter, status_code)
        execute(sql, params)
    except Exception:
        logger.exception("audit log write failed for %s %s", user_email, endpoint)
