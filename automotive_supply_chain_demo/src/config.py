"""
アプリ全体の設定値
- Unity Catalog のカタログ／スキーマ名
- Databricks FMAPI で選択可能なモデルエンドポイント一覧
- Google Material Design 準拠のカラーパレット
すべて環境変数で上書き可能（ワークスペースごとの差異を吸収するため）
"""

import os

# ──────────────────────────────────────────────
# Unity Catalog 設定
# 前提ワークスペース: E2-Demo-Field-Eng
# ──────────────────────────────────────────────

CATALOG = os.environ.get("SCM_CATALOG", "automotive_scm_demo")
SCHEMA = os.environ.get("SCM_SCHEMA", "supply_chain")

def full_table_name(table: str) -> str:
    """`catalog.schema.table` 形式の完全修飾テーブル名を返す"""
    return f"{CATALOG}.{SCHEMA}.{table}"

TABLE_SUPPLIERS = "suppliers"
TABLE_PORTS = "ports"
TABLE_ASSEMBLY_PLANTS = "assembly_plants"
TABLE_VEHICLE_MODELS = "vehicle_models"
TABLE_LOGISTICS_ROUTES = "logistics_routes"
TABLE_VEHICLE_COMPONENT_MAP = "vehicle_component_map"
TABLE_INVENTORY = "inventory"

ALL_TABLES = [
    TABLE_SUPPLIERS,
    TABLE_PORTS,
    TABLE_ASSEMBLY_PLANTS,
    TABLE_VEHICLE_MODELS,
    TABLE_LOGISTICS_ROUTES,
    TABLE_VEHICLE_COMPONENT_MAP,
    TABLE_INVENTORY,
]

# UniForm（Iceberg 互換）を有効化する Delta テーブルプロパティ
UNIFORM_TBLPROPERTIES = (
    "delta.enableIcebergCompatV2 = 'true', "
    "delta.universalFormat.enabledFormats = 'iceberg', "
    "delta.columnMapping.mode = 'name'"
)

# ──────────────────────────────────────────────
# Databricks FMAPI モデルエンドポイント
# サイドバーのプルダウンに表示する選択肢
# ──────────────────────────────────────────────

MODEL_ENDPOINTS = [
    "databricks-meta-llama-3-1-70b-instruct",
    "databricks-meta-llama-3-1-405b-instruct",
    "databricks-mixtral-8x7b-instruct",
    "databricks-dbrx-instruct",
]

DEFAULT_MODEL = MODEL_ENDPOINTS[0]

# ──────────────────────────────────────────────
# Google Material Design ライクなカラーパレット
# ──────────────────────────────────────────────

COLOR_BLUE = "#4285F4"
COLOR_RED = "#EA4335"
COLOR_YELLOW = "#FBBC05"
COLOR_GREEN = "#34A853"
COLOR_BG = "#FFFFFF"
COLOR_SURFACE = "#F8F9FA"
COLOR_TEXT = "#202124"
COLOR_TEXT_SECONDARY = "#5F6368"
COLOR_BORDER = "#DADCE0"

# ノード種別 → 色（地図・グラフで共通使用）
NODE_COLORS = {
    "Tier2": COLOR_YELLOW,
    "Tier1": COLOR_BLUE,
    "Port": COLOR_GREEN,
    "AssemblyPlant": COLOR_RED,
}

RISK_COLORS = {
    "Low": COLOR_GREEN,
    "Medium": COLOR_YELLOW,
    "High": COLOR_RED,
}

# ──────────────────────────────────────────────
# Databricks 接続情報（環境変数から取得）
# 未設定の場合はローカル SQLite によるデモモードで動作する
# ──────────────────────────────────────────────

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
DATABRICKS_HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "")

IS_DATABRICKS_CONFIGURED = bool(
    DATABRICKS_HOST and DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH
)

LOCAL_DEMO_DB_PATH = os.environ.get(
    "SCM_LOCAL_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "local_demo.db"),
)
