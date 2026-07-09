"""
ディメンションテーブル：店舗マスタ（dim_store）
- 店舗ID・店舗タイプ・店舗マネージャー名・店舗住所を保持するメタデータテーブル
- fact_sales_transactions.store_id と結合し、店舗タイプ別などの分析軸を提供する
"""

from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType
import random

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない

random.seed(42)


# ──────────────────────────────────────────────
# 店舗タイプ・所在地・マネージャー名のサンプル値
# ──────────────────────────────────────────────

STORE_TYPES = ["旗艦店", "都市型", "郊外型", "アウトレット"]

CITIES = [
    "東京", "大阪", "名古屋", "福岡", "札幌", "仙台", "広島", "京都",
    "ニューヨーク", "ロサンゼルス", "ロンドン", "パリ", "上海", "シンガポール",
]

LAST_NAMES = [
    "田中", "鈴木", "佐藤", "山田", "伊藤", "渡辺", "中村", "小林",
    "Smith", "Johnson", "Williams", "Brown", "Chen", "Wang",
]
FIRST_NAMES = [
    "太郎", "花子", "健一", "由美", "翔", "さくら",
    "James", "Mary", "David", "Lisa", "Wei", "Hana",
]


# ──────────────────────────────────────────────
# ディメンションテーブルのスキーマ定義
# ──────────────────────────────────────────────

dim_store_schema = StructType([
    StructField("store_id",           StringType(), nullable=False),  # 店舗ID（主キー）
    StructField("store_type",         StringType(), nullable=True),   # 店舗タイプ
    StructField("store_manager_name", StringType(), nullable=True),   # 店舗マネージャー名
    StructField("store_address",      StringType(), nullable=True),   # 店舗住所
])


# ──────────────────────────────────────────────
# 店舗マスタデータ生成（50店舗：ST001〜ST050、fact側と共通の採番）
# ──────────────────────────────────────────────

N_STORES = 50

store_rows = []
for i in range(1, N_STORES + 1):
    store_id = f"ST{str(i).zfill(3)}"                             # ST001〜ST050（fact_sales_transactionsと共通）
    city     = random.choice(CITIES)
    manager  = random.choice(LAST_NAMES) + " " + random.choice(FIRST_NAMES)

    store_rows.append(Row(
        store_id=store_id,
        store_type=random.choice(STORE_TYPES),
        store_manager_name=manager,
        store_address=f"{city} {random.randint(1, 9)}-{random.randint(1, 30)}-{random.randint(1, 20)}",
    ))

df_dim_store = spark.createDataFrame(store_rows, schema=dim_store_schema)

print(f"=== dim_store（{df_dim_store.count()}件） ===")
df_dim_store.show(10, truncate=False)


# ──────────────────────────────────────────────
# Delta テーブルとして保存（Databricks Free Edition / Hiveメタストア）
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS retail")

(
    df_dim_store
    .write
    .format("delta")                     # Delta Lake 形式で保存
    .mode("overwrite")                   # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")   # スキーマ変更も上書き許可
    .saveAsTable("retail.dim_store")
)

print("retail.dim_store の保存が完了しました")
# spark.stop() はここで呼ばない（Databricksのクラスターがセッションを管理するため）
