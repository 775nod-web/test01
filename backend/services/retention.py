"""Retention Actions page, including CSV export."""

from __future__ import annotations

import csv
import io
from typing import Optional

from backend.db import QueryEngine

MAX_LIMIT = 2000
MAX_EXPORT_ROWS = 5000

_CSV_COLUMNS = [
    "customer_id",
    "value_segment",
    "risk_segment",
    "risk_score",
    "primary_driver",
    "secondary_driver",
    "recommended_action",
    "recommended_channel",
    "human_review_required",
    "estimated_value_at_risk",
    "action_priority_rank",
    "priority_tier",
]


def list_retention_actions(
    engine: QueryEngine,
    risk_segment: Optional[str] = None,
    value_segment: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    safe_limit = max(1, min(limit, MAX_LIMIT))
    safe_offset = max(0, offset)
    return engine.run(
        "retention_actions.sql",
        risk_segment=risk_segment,
        value_segment=value_segment,
        limit=safe_limit,
        offset=safe_offset,
    )


def export_retention_actions_csv(
    engine: QueryEngine,
    risk_segment: Optional[str] = None,
    value_segment: Optional[str] = None,
) -> str:
    rows = engine.run(
        "retention_actions.sql",
        risk_segment=risk_segment,
        value_segment=value_segment,
        limit=MAX_EXPORT_ROWS,
        offset=0,
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()
