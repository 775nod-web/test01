"""Executive Overview page: KPIs and the three supporting charts."""

from __future__ import annotations

from backend.db import QueryEngine


def get_kpis(engine: QueryEngine) -> dict:
    rows = engine.run("executive_overview.sql")
    if not rows:
        raise LookupError("executive_kpis returned no rows")
    return rows[0]


def get_risk_distribution(engine: QueryEngine) -> list[dict]:
    return engine.run("risk_distribution.sql")


def get_value_risk_matrix(engine: QueryEngine) -> list[dict]:
    return engine.run("value_risk_matrix.sql")


def get_top_risk_drivers(engine: QueryEngine) -> list[dict]:
    return engine.run("top_risk_drivers.sql")
