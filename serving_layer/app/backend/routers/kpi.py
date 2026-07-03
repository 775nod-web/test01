"""経営層向け: 日次KPI (`gold.daily_kpi`)。"""

from datetime import date, timedelta

from fastapi import APIRouter, Query

from ..db import qualified_table, run_query
from ..models import DailyKpi

router = APIRouter(prefix="/daily-kpi", tags=["daily-kpi"])


def _latest_kpi_date() -> date | None:
    rows = run_query(f"SELECT MAX(kpi_date) AS max_date FROM {qualified_table('daily_kpi')}")
    return rows[0]["max_date"] if rows else None


@router.get("", response_model=list[DailyKpi])
def list_daily_kpi(
    days: int = Query(30, ge=1, le=366, description="データ内の最新日から遡って何日分を返すか"),
    start: date | None = Query(None, description="開始日を明示指定する場合(指定時は days を無視)"),
    end: date | None = Query(None, description="終了日を明示指定する場合(指定時は days を無視)"),
) -> list[DailyKpi]:
    # 実行環境の「今日」ではなく、テーブルに実在する最新日付を基準にする。
    # サンプル/デモデータは実際のカレンダー日付と無関係な期間で作られることが
    # あるため、date.today() を基準にすると「直近N日」が空振りしてしまう。
    # start/end を明示指定しない限り、フロントエンドは days だけを渡すこと。
    end_date = end or _latest_kpi_date() or date.today()
    start_date = start or (end_date - timedelta(days=days))

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
