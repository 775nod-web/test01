"""Serving layer の実行時設定。

Databricks Apps 上ではホスト・認証情報が環境変数として自動注入される。
ローカル開発時は同名の環境変数を .env / シェルで設定して動かす。
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    server_hostname: str
    http_path: str
    access_token: str | None
    client_id: str | None
    client_secret: str | None
    catalog: str
    schema: str


def get_settings() -> Settings:
    return Settings(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ.get("DATABRICKS_TOKEN"),
        client_id=os.environ.get("DATABRICKS_CLIENT_ID"),
        client_secret=os.environ.get("DATABRICKS_CLIENT_SECRET"),
        catalog=os.environ.get("DATABRICKS_CATALOG", "workspace"),
        schema=os.environ.get("DATABRICKS_GOLD_SCHEMA", "gold"),
    )
