"""
データアクセス層

- 本番（Databricks Apps 上で実行）: Databricks SQL Warehouse に接続し、
  Unity Catalog 上の Delta（UniForm/Iceberg 有効）テーブルを直接クエリする。
- ローカル開発 / 動作確認: DATABRICKS_* 環境変数が無い場合は、同じスキーマの
  SQLite データベースを自動生成してフォールバックする（UIの見た目や操作感を
  Databricks 環境なしで確認するためのモード）。

CRUD 操作（INSERT/UPDATE/DELETE）もこのモジュール経由で行い、
Databricks / SQLite のどちらに対しても同じ呼び出し方で動作するようにする。
"""

import os
import sqlite3
import threading

import pandas as pd
import streamlit as st

from . import config, sample_data


# ──────────────────────────────────────────────
# ローカルデモモード（SQLite）
# ──────────────────────────────────────────────

_local_lock = threading.Lock()


def _local_db_path() -> str:
    path = config.LOCAL_DEMO_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _init_local_db_if_needed():
    """ローカル SQLite DB が未作成、または空の場合にサンプルデータを投入する"""
    path = _local_db_path()
    with _local_lock:
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='suppliers'"
            )
            exists = cur.fetchone() is not None
            if exists:
                return
            tables = sample_data.generate_all()
            for name, df in tables.items():
                df.to_sql(name, conn, if_exists="replace", index=False)
            conn.commit()
        finally:
            conn.close()


class _LocalConnection:
    """SQLite 用の薄いラッパー（Databricks SQL Connector と同じインタフェースを提供）"""

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        conn = sqlite3.connect(_local_db_path())
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()):
        conn = sqlite3.connect(_local_db_path())
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()


class _DatabricksConnection:
    """Databricks SQL Warehouse 用ラッパー（databricks-sql-connector 使用）"""

    def __init__(self):
        from databricks import sql as dbsql
        self._dbsql = dbsql

    def _connect(self):
        return self._dbsql.connect(
            server_hostname=config.DATABRICKS_HOST,
            http_path=config.DATABRICKS_HTTP_PATH,
            access_token=config.DATABRICKS_TOKEN,
        )

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall_arrow().to_pandas()

    def execute(self, sql: str, params: tuple = ()):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)


@st.cache_resource
def get_connection():
    """Databricks 接続情報があれば本番接続、無ければローカル SQLite フォールバックを返す"""
    if config.IS_DATABRICKS_CONFIGURED:
        return _DatabricksConnection()
    _init_local_db_if_needed()
    return _LocalConnection()


def is_demo_mode() -> bool:
    return not config.IS_DATABRICKS_CONFIGURED


def qualified(table: str) -> str:
    """本番は catalog.schema.table、デモモードはテーブル名のみを返す"""
    if config.IS_DATABRICKS_CONFIGURED:
        return config.full_table_name(table)
    return table


# ──────────────────────────────────────────────
# 汎用クエリヘルパー
# ──────────────────────────────────────────────

def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    return get_connection().query(sql, params)


def run_execute(sql: str, params: tuple = ()):
    get_connection().execute(sql, params)


# ──────────────────────────────────────────────
# テーブル別の取得ヘルパー
# ──────────────────────────────────────────────

def get_suppliers() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_SUPPLIERS)}")


def get_ports() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_PORTS)}")


def get_assembly_plants() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_ASSEMBLY_PLANTS)}")


def get_vehicle_models() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_VEHICLE_MODELS)}")


def get_logistics_routes() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_LOGISTICS_ROUTES)}")


def get_vehicle_component_map() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_VEHICLE_COMPONENT_MAP)}")


def get_inventory() -> pd.DataFrame:
    return run_query(f"SELECT * FROM {qualified(config.TABLE_INVENTORY)}")


# ──────────────────────────────────────────────
# 在庫（inventory）テーブルの CRUD
# ──────────────────────────────────────────────

def insert_inventory_item(item: dict):
    table = qualified(config.TABLE_INVENTORY)
    cols = ", ".join(item.keys())
    placeholders = ", ".join(["?"] * len(item)) if is_demo_mode() else ", ".join(["%s"] * len(item))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    run_execute(sql, tuple(item.values()))


def update_inventory_item(inventory_id: str, updates: dict):
    table = qualified(config.TABLE_INVENTORY)
    ph = "?" if is_demo_mode() else "%s"
    set_clause = ", ".join([f"{k} = {ph}" for k in updates.keys()])
    sql = f"UPDATE {table} SET {set_clause} WHERE inventory_id = {ph}"
    run_execute(sql, tuple(updates.values()) + (inventory_id,))


def delete_inventory_item(inventory_id: str):
    table = qualified(config.TABLE_INVENTORY)
    ph = "?" if is_demo_mode() else "%s"
    sql = f"DELETE FROM {table} WHERE inventory_id = {ph}"
    run_execute(sql, (inventory_id,))


# ──────────────────────────────────────────────
# サプライヤー（suppliers）テーブルの CRUD
# ──────────────────────────────────────────────

def insert_supplier(item: dict):
    table = qualified(config.TABLE_SUPPLIERS)
    cols = ", ".join(item.keys())
    placeholders = ", ".join(["?"] * len(item)) if is_demo_mode() else ", ".join(["%s"] * len(item))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    run_execute(sql, tuple(item.values()))


def update_supplier(supplier_id: str, updates: dict):
    table = qualified(config.TABLE_SUPPLIERS)
    ph = "?" if is_demo_mode() else "%s"
    set_clause = ", ".join([f"{k} = {ph}" for k in updates.keys()])
    sql = f"UPDATE {table} SET {set_clause} WHERE supplier_id = {ph}"
    run_execute(sql, tuple(updates.values()) + (supplier_id,))


def delete_supplier(supplier_id: str):
    table = qualified(config.TABLE_SUPPLIERS)
    ph = "?" if is_demo_mode() else "%s"
    sql = f"DELETE FROM {table} WHERE supplier_id = {ph}"
    run_execute(sql, (supplier_id,))
