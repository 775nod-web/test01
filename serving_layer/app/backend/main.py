"""Serving layer の FastAPI エントリポイント。

Databricks Apps 上ではこのプロセス1つで API と React ビルド成果物の
両方を配信する。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import data_quality, failed_payments, kpi, sales

app = FastAPI(title="Gold Layer Serving API", version="1.0.0")

app.include_router(kpi.router, prefix="/api/v1")
app.include_router(sales.router, prefix="/api/v1")
app.include_router(failed_payments.router, prefix="/api/v1")
app.include_router(data_quality.router, prefix="/api/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
