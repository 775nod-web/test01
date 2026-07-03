"""事業企画・プロダクト向け: プラン別売上 (`gold.sales_per_plan`)。"""

from collections import defaultdict

from fastapi import APIRouter, Query

from ..db import qualified_table, run_query
from ..models import SalesPerPlan

router = APIRouter(prefix="/sales-per-plan", tags=["sales-per-plan"])


def _latest_sales_month():
    rows = run_query(f"SELECT MAX(sales_month) AS max_month FROM {qualified_table('sales_per_plan')}")
    return rows[0]["max_month"] if rows else None


@router.get("", response_model=list[SalesPerPlan])
def list_sales_per_plan(
    months: int = Query(12, ge=1, le=36, description="直近何ヶ月分を返すか"),
) -> list[SalesPerPlan]:
    # 実行環境の「今日」ではなく、テーブルに実在する最新月を基準にする。
    # サンプル/デモデータは実際のカレンダー日付と無関係な期間で作られることが
    # あるため、current_date() を基準にすると「直近Nヶ月」が空振りしてしまう。
    latest_month = _latest_sales_month()
    if latest_month is None:
        return []

    sql_text = f"""
        SELECT
            sales_month, plan_type, total_revenue, transaction_count,
            success_count, failed_count, avg_transaction_amount,
            new_subscriber_count, churned_subscriber_count,
            active_subscriber_count, failed_payment_rate
        FROM {qualified_table('sales_per_plan')}
        WHERE sales_month >= add_months(date_trunc('month', %(latest_month)s), -%(months)s)
        ORDER BY sales_month DESC, plan_type
    """
    rows = run_query(sql_text, {"latest_month": latest_month, "months": months})

    # プランごとに月次順で並べ、前月比 (MoM) を算出してから返却する。
    by_plan: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_plan[row["plan_type"]].append(row)

    result: list[SalesPerPlan] = []
    for plan_rows in by_plan.values():
        # sales_month 昇順に並べ替えて MoM を計算
        plan_rows_sorted = sorted(plan_rows, key=lambda r: r["sales_month"])
        prev_revenue: float | None = None
        for row in plan_rows_sorted:
            mom = None
            if prev_revenue is not None and prev_revenue != 0:
                mom = (row["total_revenue"] - prev_revenue) / prev_revenue
            result.append(SalesPerPlan(**row, revenue_mom_change_rate=mom))
            prev_revenue = row["total_revenue"]

    result.sort(key=lambda r: (r.sales_month, r.plan_type), reverse=True)
    return result
