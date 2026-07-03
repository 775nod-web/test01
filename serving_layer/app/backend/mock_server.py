"""ローカル動作確認用のモックサーバー。

実際の Databricks SQL Warehouse に接続できない開発環境（このコーディング
演習環境を含む）でも、フロントエンドの見た目とAPI契約を検証できるように
Gold layer のテーブル定義に沿ったダミーデータを返す。

本番 (Databricks Apps) では使用しない。`backend/main.py` が本来のエントリ
ポイントであり、これは `uvicorn backend.mock_server:app` で個別に起動する。
"""

import random
from datetime import date, timedelta

from fastapi import FastAPI

from .models import DailyKpi, DataQualitySummary, FailedPaymentUser, SalesPerPlan

app = FastAPI(title="Gold Layer Serving API (mock)")

random.seed(42)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/daily-kpi", response_model=list[DailyKpi])
def daily_kpi(start: str | None = None, end: str | None = None) -> list[DailyKpi]:
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

    rows = []
    d = start_date
    dau_base = 4200
    while d <= end_date:
        dau = dau_base + random.randint(-150, 220)
        new_signup = random.randint(20, 60)
        new_paid = random.randint(3, 15)
        rows.append(
            DailyKpi(
                kpi_date=d,
                dau=dau,
                new_signup_count=new_signup,
                total_paid_users=1800 + random.randint(-30, 40),
                total_free_users=9500 + random.randint(-100, 150),
                daily_revenue=round(random.uniform(350000, 620000), 2),
                upgrade_click_count=random.randint(40, 120),
                cancel_click_count=random.randint(10, 45),
                new_paid_conversion_count=new_paid,
                churn_count=random.randint(2, 18),
                free_to_paid_rate=round(new_paid / new_signup, 4) if new_signup else None,
            )
        )
        dau_base += random.randint(-20, 25)
        d += timedelta(days=1)
    return rows


@app.get("/api/v1/sales-per-plan", response_model=list[SalesPerPlan])
def sales_per_plan(months: int = 12) -> list[SalesPerPlan]:
    plans = {
        "starter": {"base": 900000, "failed_rate": 0.03},
        "pro": {"base": 2600000, "failed_rate": 0.06},
        "enterprise": {"base": 4100000, "failed_rate": 0.14},
    }
    rows = []
    today = date.today().replace(day=1)
    for i in range(months):
        month = _add_months(today, -i)
        for plan, cfg in plans.items():
            revenue = cfg["base"] * (1 + random.uniform(-0.08, 0.08)) * (1 - 0.01 * i if plan == "enterprise" else 1)
            success = random.randint(300, 900)
            failed = int(success * cfg["failed_rate"] * random.uniform(0.7, 1.3))
            total_txn = success + failed
            rows.append(
                SalesPerPlan(
                    sales_month=month,
                    plan_type=plan,
                    total_revenue=round(revenue, 2),
                    transaction_count=total_txn,
                    success_count=success,
                    failed_count=failed,
                    avg_transaction_amount=round(revenue / success, 2) if success else None,
                    new_subscriber_count=random.randint(20, 80),
                    churned_subscriber_count=random.randint(5, 40),
                    active_subscriber_count=random.randint(500, 2500),
                    failed_payment_rate=round(failed / total_txn, 4) if total_txn else None,
                )
            )
    return rows


_SEGMENTS = ["individual", "smb", "enterprise"]
_COUNTRIES = ["JP"]
_PLANS = ["starter", "pro", "enterprise"]
_STATUSES = ["failed", "pending"]


@app.get("/api/v1/failed-payment-users", response_model=list[FailedPaymentUser])
def failed_payment_users(
    risk: str = "all", plan_type: str | None = None, user_segment: str | None = None
) -> list[FailedPaymentUser]:
    rows = []
    for i in range(1, 61):
        is_high_risk = random.random() < 0.4
        row = FailedPaymentUser(
            user_id=f"U{i:04d}",
            plan_type=random.choice(_PLANS),
            country_code=random.choice(_COUNTRIES),
            user_segment=random.choice(_SEGMENTS),
            is_active=random.random() < 0.85,
            total_failed_count=random.randint(1, 6),
            total_success_count=random.randint(0, 30),
            latest_payment_date=date.today() - timedelta(days=random.randint(0, 60)),
            latest_payment_status=random.choice(_STATUSES),
            latest_amount=round(random.uniform(980, 15800), 2),
            has_recent_cancel_click=random.random() < 0.3,
            churn_risk_flag=is_high_risk,
        )
        if plan_type and row.plan_type != plan_type:
            continue
        if user_segment and row.user_segment != user_segment:
            continue
        if risk == "high" and not row.churn_risk_flag:
            continue
        if risk == "low" and row.churn_risk_flag:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r.total_failed_count, reverse=True)
    return rows


_TABLES = ["bronze_orders", "bronze_products", "bronze_users", "silver_users"]
_CHECKS = ["not_null_check", "duplicate_key_check", "referential_integrity_check", "range_check"]


@app.get("/api/v1/data-quality-summary", response_model=list[DataQualitySummary])
def data_quality_summary(days: int = 14) -> list[DataQualitySummary]:
    rows = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        for table in _TABLES:
            for check in _CHECKS:
                checked = random.randint(500, 2000)
                failed = int(checked * random.choice([0, 0, 0.005, 0.03, 0.12]))
                rows.append(
                    DataQualitySummary(
                        run_date=d,
                        source_table=table,
                        dq_check_name=check,
                        failed_record_count=failed,
                        checked_record_count=checked,
                        failed_rate=round(failed / checked, 4) if checked else None,
                    )
                )
    return rows


def _add_months(d: date, delta: int) -> date:
    month = d.month - 1 + delta
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)
