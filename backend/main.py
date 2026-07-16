"""Databricks Apps上で動作するFastAPIエントリーポイント。

デプロイ前ビルド方式を採用する。Reactのビルドはこのプロセスの起動時には行わず、
`scripts/prepare_deploy.sh` 等で事前に生成された `frontend/dist` を配信するだけである。

- development モード（既定）：`frontend/dist` が無くてもAPIのみで起動できる
  （Viteの開発サーバーと併用する想定）。
- production モード（`APP_ENV=production`）：`frontend/dist/index.html` が無い場合は
  UIが欠落したまま正常起動したように見せず、明確なエラーで起動を失敗させる。
"""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.config import (
    APP_ENV_PRODUCTION,
    resolve_app_env,
    resolve_host,
    resolve_port,
)

logger = logging.getLogger(__name__)

FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

PREPARE_DEPLOY_HINT = (
    "frontend/dist/index.html が見つかりません。\n"
    "scripts/prepare_deploy.sh を実行してから再デプロイしてください。"
)


class FrontendBuildMissingError(RuntimeError):
    """productionモードでReactのビルド成果物が見つからない場合に送出する。"""


def create_app(
    app_env: str | None = None,
    frontend_dist_dir: Path | None = None,
) -> FastAPI:
    resolved_env = app_env if app_env is not None else resolve_app_env()
    dist_dir = frontend_dist_dir if frontend_dist_dir is not None else FRONTEND_DIST_DIR
    index_html = dist_dir / "index.html"

    app = FastAPI(title="顧客休眠予兆・次アクション支援デモ")
    app.include_router(api_router, prefix="/api")

    if index_html.is_file():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
    elif resolved_env == APP_ENV_PRODUCTION:
        logger.error(PREPARE_DEPLOY_HINT)
        raise FrontendBuildMissingError(PREPARE_DEPLOY_HINT)
    # development モードでは dist が無くてもAPIのみで起動する。

    return app


app = create_app()


def main() -> None:
    uvicorn.run(app, host=resolve_host(), port=resolve_port())


if __name__ == "__main__":
    main()
