"""Gold layer のテーブル定義に1対1で対応するレスポンススキーマ。

カラム名・Nullable 有無は Gold layer 設計メモに準拠する。存在しない
カラムを追加したり、勝手に改名したりしないこと。
"""

from datetime import date

from pydantic import BaseModel


class DailyKpi(BaseModel):
    kpi_date: date
    dau: int
    new_signup_count: int
    total_paid_users: int
    total_free_users: int
    daily_revenue: float
    upgrade_click_count: int
    cancel_click_count: int
    new_paid_conversion_count: int
    churn_count: int
    free_to_paid_rate: float | None = None


class SalesPerPlan(BaseModel):
    sales_month: date
    plan_type: str
    total_revenue: float
    transaction_count: int
    success_count: int
    failed_count: int
    avg_transaction_amount: float | None = None
    new_subscriber_count: int
    churned_subscriber_count: int
    active_subscriber_count: int
    failed_payment_rate: float | None = None
    # API 側で付加する派生値 (Gold テーブルには存在しない)
    revenue_mom_change_rate: float | None = None


class FailedPaymentUser(BaseModel):
    user_id: str
    plan_type: str | None = None
    country_code: str | None = None
    user_segment: str | None = None
    is_active: bool | None = None
    total_failed_count: int
    total_success_count: int
    latest_payment_date: date | None = None
    latest_payment_status: str | None = None
    latest_amount: float | None = None
    has_recent_cancel_click: bool
    churn_risk_flag: bool


class DataQualitySummary(BaseModel):
    run_date: date
    source_table: str
    dq_check_name: str
    issue_count: int
    total_records: int
    description: str | None = None
    issue_rate: float | None = None
