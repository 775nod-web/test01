"""Databricks SQL Warehouse への接続ヘルパー。

Databricks Apps の実行環境では、アプリのサービスプリンシパルの認証情報が
自動的に環境へ注入される。`databricks.sdk.core.Config()` は引数なしで
その認証情報とワークスペースホストを解決できるため、ここでは
Warehouse ID のみを明示的に指定すればよい。

参考: Databricks公式のApps用サンプルテンプレート（data-app-template等）が
採用している `credentials_provider=lambda: cfg.authenticate` のパターンに
準拠している。ローカル開発時は `databricks configure` 済みのプロファイル、
または DATABRICKS_HOST / DATABRICKS_TOKEN 環境変数からも解決される。
"""

import os
from functools import lru_cache

from databricks import sql
from databricks.sdk.core import Config

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "50153ad923fecd73")
TABLE_PREFIX = os.environ.get("GOLD_TABLE_PREFIX", "gold")


@lru_cache(maxsize=1)
def _get_config() -> Config:
    """Config()は生成時に認証情報を解決しようとして即座に例外を送出しうるため、
    実際にDB接続が必要になるまで遅延させる（/api/healthなどDB不要なエンドポイントを
    未認証のローカル環境でも壊さないため）"""
    return Config()


def get_connection():
    """gold.* Delta テーブルが置かれた Warehouse への接続を返す（呼び出し側でclose/with管理する）"""
    config = _get_config()
    return sql.connect(
        server_hostname=config.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: config.authenticate,
    )


def qualified_table(table_name: str) -> str:
    """gold_daily_store_sales のような表名を GOLD_TABLE_PREFIX で修飾する"""
    return f"{TABLE_PREFIX}.{table_name}"
