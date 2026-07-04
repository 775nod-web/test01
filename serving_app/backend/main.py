"""Serving layer API + フロントエンド配信

Databricks Apps は単一プロセス起動が前提のため、このFastAPIアプリが
1) /api/* のGold layerデータ配信API と
2) ビルド済みReact(TypeScript)フロントエンドの静的配信
の両方を兼ねる。
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import queries

logger = logging.getLogger("serving_app")

app = FastAPI(title="Retail Gold Layer Serving API")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/daily-store-sales")
def daily_store_sales() -> list[dict]:
    try:
        return queries.fetch_daily_store_sales()
    except Exception as exc:  # noqa: BLE001 - Gold layer接続失敗をそのままAPIエラーに変換する
        logger.exception("failed to fetch gold_daily_store_sales")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/category-sales")
def category_sales() -> list[dict]:
    try:
        return queries.fetch_category_sales()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to fetch gold_category_sales")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/store-ranking")
def store_ranking() -> list[dict]:
    try:
        return queries.fetch_store_ranking()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to fetch gold_store_ranking")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/unregistered-master-report")
def unregistered_master_report() -> list[dict]:
    try:
        return queries.fetch_unregistered_master_report()
    except Exception as exc:  # noqa: BLE001
        logger.exception("failed to fetch gold_unregistered_master_report")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ビルド済みフロントエンド（frontend/dist）が存在する場合のみ静的配信を有効化する。
# ローカルでバックエンドのみ動かしてAPIを確認する場合はdistが無くてもエラーにならない。
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
