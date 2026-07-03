"""CS・営業向け: 決済失敗ユーザーのアクションリスト (`gold.failed_payment_user`)。"""

from typing import Literal

from fastapi import APIRouter, Query

from ..db import qualified_table, run_query
from ..models import FailedPaymentUser

router = APIRouter(prefix="/failed-payment-users", tags=["failed-payment-users"])


@router.get("", response_model=list[FailedPaymentUser])
def list_failed_payment_users(
    risk: Literal["all", "high", "low"] = Query("all", description="churn_risk_flag によるフィルタ"),
    plan_type: str | None = Query(None),
    user_segment: str | None = Query(None),
) -> list[FailedPaymentUser]:
    conditions = ["1=1"]
    params: dict[str, object] = {}

    if risk == "high":
        conditions.append("churn_risk_flag = true")
    elif risk == "low":
        conditions.append("churn_risk_flag = false")

    if plan_type:
        conditions.append("plan_type = %(plan_type)s")
        params["plan_type"] = plan_type

    if user_segment:
        conditions.append("user_segment = %(user_segment)s")
        params["user_segment"] = user_segment

    sql_text = f"""
        SELECT
            user_id, plan_type, country_code, user_segment, is_active,
            total_failed_count, total_success_count, latest_payment_date,
            latest_payment_status, latest_amount, has_recent_cancel_click,
            churn_risk_flag
        FROM {qualified_table('failed_payment_user')}
        WHERE {' AND '.join(conditions)}
        ORDER BY total_failed_count DESC, latest_payment_date DESC
    """
    rows = run_query(sql_text, params)
    return [FailedPaymentUser(**row) for row in rows]
