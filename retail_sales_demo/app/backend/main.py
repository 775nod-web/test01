"""Serving layer バックエンド（FastAPI）。

Databricks Apps上で `uvicorn backend.main:app` として起動される想定。
フロントエンド（frontend/dist のビルド成果物）を同一プロセスから静的配信する。
"""
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import queries
from .config import FORWARDED_USER_HEADER, RECONCILE_JOB_ID
from .db import get_client

app = FastAPI(title="Retail Sales Serving Layer API")


def _current_user_email(request: Request) -> str | None:
    return request.headers.get(FORWARDED_USER_HEADER)


def _allowed_stores(request: Request) -> list[str] | None:
    """UC行フィルタが有効な環境では、DB側で自動的に絞り込まれるため
    ここではNoneを返してAPI側フィルタを無効化してよい。
    行フィルタが未対応（フォールバック運用）の場合のみ実際にマッピングを引く。
    フォールバックを使うかどうかは環境変数 ROW_FILTER_ENABLED_BY_UC で切り替える想定だが、
    未接続で確認できていないため、デフォルトはAPI側フィルタを有効（安全側）にしている。
    """
    import os

    if os.environ.get("ROW_FILTER_ENABLED_BY_UC", "false").lower() == "true":
        return None
    return queries.get_allowed_stores(_current_user_email(request))


@app.get("/api/kpi-summary")
def kpi_summary(request: Request, date_from: str | None = None, date_to: str | None = None, store_id: str | None = None):
    date_to = date_to or date.today().isoformat()
    date_from = date_from or (date.today() - timedelta(days=30)).isoformat()
    result = queries.get_kpi_summary(date_from, date_to, store_id, _allowed_stores(request))
    queries.log_access(_current_user_email(request), "kpi-summary", store_id)
    return result


@app.get("/api/daily-store-sales")
def daily_store_sales(request: Request, date_from: str | None = None, date_to: str | None = None, store_id: str | None = None):
    date_to = date_to or date.today().isoformat()
    date_from = date_from or (date.today() - timedelta(days=30)).isoformat()
    result = queries.get_daily_store_sales(date_from, date_to, store_id, _allowed_stores(request))
    queries.log_access(_current_user_email(request), "daily-store-sales", store_id)
    return result


@app.get("/api/category-sales")
def category_sales(request: Request):
    queries.log_access(_current_user_email(request), "category-sales", None)
    return queries.get_category_sales()


@app.get("/api/store-ranking")
def store_ranking(request: Request, limit: int = 20):
    result = queries.get_store_ranking(limit, _allowed_stores(request))
    queries.log_access(_current_user_email(request), "store-ranking", None)
    return result


@app.get("/api/quarantine-report")
def quarantine_report(request: Request, issue_type: str | None = None):
    result = queries.get_quarantine_report(issue_type)
    queries.log_access(_current_user_email(request), "quarantine-report", None)
    return result


@app.get("/api/quarantine-summary")
def quarantine_summary(request: Request):
    queries.log_access(_current_user_email(request), "quarantine-summary", None)
    return queries.get_quarantine_summary()


@app.get("/api/alerts")
def alerts(request: Request):
    queries.log_access(_current_user_email(request), "alerts", None)
    return queries.get_alerts()


@app.post("/api/reconcile-quarantine")
def reconcile_quarantine():
    """quarantine自動再照合ジョブ（jobs/quarantine_reconciliation_job.py）をトリガーする。

    RECONCILE_JOB_ID未設定の場合はジョブ未作成として明示的にエラーを返す。
    """
    if not RECONCILE_JOB_ID:
        return {"triggered": False, "reason": "RECONCILE_JOB_ID is not configured"}
    client = get_client()
    run = client.jobs.run_now(job_id=int(RECONCILE_JOB_ID))
    return {"triggered": True, "run_id": run.run_id}


# フロントエンドのビルド成果物 (frontend/dist) を配信する。
# ビルド前（開発時）はディレクトリが存在しないためスキップする。
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
