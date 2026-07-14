"""Segment Explorer and Customer 360 pages."""

from __future__ import annotations

from typing import Optional

from backend.db import QueryEngine

MAX_LIMIT = 2000


def list_customers(
    engine: QueryEngine,
    risk_segment: Optional[str] = None,
    value_segment: Optional[str] = None,
    max_product_count: Optional[int] = None,
    balance_decline_pct: Optional[float] = None,
    card_spend_decline_pct: Optional[float] = None,
    app_decline_pct: Optional[float] = None,
    min_complaints_90d: Optional[int] = None,
    limit: int = 200,
) -> list[dict]:
    safe_limit = max(1, min(limit, MAX_LIMIT))
    return engine.run(
        "segment_explorer.sql",
        risk_segment=risk_segment,
        value_segment=value_segment,
        max_product_count=max_product_count,
        balance_decline_pct=balance_decline_pct,
        card_spend_decline_pct=card_spend_decline_pct,
        app_decline_pct=app_decline_pct,
        min_complaints_90d=min_complaints_90d,
        limit=safe_limit,
    )


def get_customer_detail(engine: QueryEngine, customer_id: str) -> Optional[dict]:
    summary_rows = engine.run("customer_360_summary.sql", customer_id=customer_id)
    if not summary_rows:
        return None
    summary = dict(summary_rows[0])
    summary["trends"] = engine.run("customer_trends.sql", customer_id=customer_id)
    summary["contact_history"] = engine.run("customer_contact_history.sql", customer_id=customer_id)
    return summary
