"""Serving layer の実行時設定。

Databricks Apps は `DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` を
自動注入しない。自動注入されるのはアプリ自身のワークスペース認証情報
（`DATABRICKS_HOST` とOAuthクライアント資格情報）のみで、SQL Warehouse の
接続先（ホスト名・HTTP Path）は `databricks.sdk.WorkspaceClient` を使って
ウェアハウスIDから都度解決する。ウェアハウスIDは `app.yaml` の
`resources` ブロックと `env: - valueFrom` の組み合わせで
`DATABRICKS_WAREHOUSE_ID` として渡す。

ローカル開発時は `DATABRICKS_WAREHOUSE_ID` に加え、SDKの認証情報
（`databricks auth login` 済みのプロファイル、または
`DATABRICKS_HOST`/`DATABRICKS_TOKEN`）を環境に設定しておけばよい。
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    warehouse_id: str
    catalog: str
    schema: str


def get_settings() -> Settings:
    return Settings(
        warehouse_id=os.environ["DATABRICKS_WAREHOUSE_ID"],
        catalog=os.environ.get("DATABRICKS_CATALOG", "workspace"),
        schema=os.environ.get("DATABRICKS_GOLD_SCHEMA", "gold"),
    )
