"""経営層向け: 日次KPI (`gold.daily_kpi`)。"""

from datetime import date, timedelta

from fastapi import APIRouter, Query

from ..db import qualified_table, run_query
from ..models import DailyKpi

router = APIRouter(prefix="/daily-kpi", tags=["daily-kpi"])


@router.get("", response_model=list[DailyKpi])
def list_daily_kpi(
    start: date | None = Query(None, description="開始日 (省略時は end の30日前)"),
    end: date | None = Query(None, description="終了日 (省略時は今日)"),
) -> list[DailyKpi]:
    end_date = end or date.today()
    start_date = start or (end_date - timedelta(days=30))

    sql_text = f"""
        SELECT
            kpi_date, dau, new_signup_count, total_paid_users, total_free_users,
            daily_revenue, upgrade_click_count, cancel_click_count,
            new_paid_conversion_count, churn_count, free_to_paid_rate
        FROM {qualified_table('daily_kpi')}
        WHERE kpi_date BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY kpi_date
    """
    rows = run_query(sql_text, {"start_date": start_date, "end_date": end_date})
    return [DailyKpi(**row) for row in rows]
