"""
ファクトテーブル：売上トランザクション（fact_sales_transactions）
- 全世界の店舗POSから収集した、過去1ヶ月分の典型的な売上取引を模擬生成する
- 粒度：1取引 = 1レコード（transaction_id が主キー）
"""

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
)
import random
from datetime import datetime, timedelta

# Databricks ノートブックでは spark はクラスターから自動注入されるため
# SparkSession.builder は呼ばない（呼ぶと INVALID_CONNECT_URL エラーになる）

random.seed(42)


# ──────────────────────────────────────────────
# 対象期間：直近1ヶ月分（POSは毎分データを送信するため分単位で日時を生成）
# ──────────────────────────────────────────────

PERIOD_END   = datetime(2026, 7, 9, 0, 0, 0)
PERIOD_START = PERIOD_END - timedelta(days=30)


def random_datetime(start: datetime, end: datetime) -> datetime:
    """start〜end の範囲でランダムな日時（分単位）を返す"""
    total_minutes = int((end - start).total_seconds() // 60)
    return start + timedelta(minutes=random.randint(0, total_minutes))


# ──────────────────────────────────────────────
# 参照値（dim_store 側と共通の store_id 採番範囲を使用し、後で結合できるようにする）
# ──────────────────────────────────────────────

STORE_IDS    = [f"ST{str(i).zfill(3)}" for i in range(1, 51)]     # ST001〜ST050（dim_storeと共通）
PRODUCT_SKUS = [f"SKU{str(i).zfill(4)}" for i in range(1, 201)]   # SKU0001〜SKU0200


# ──────────────────────────────────────────────
# ファクトテーブルのスキーマ定義
# ──────────────────────────────────────────────

fact_sales_schema = StructType([
    StructField("transaction_id",       StringType(),    nullable=False),  # 取引ID（主キー）
    StructField("transaction_datetime", TimestampType(), nullable=False),  # 取引日時
    StructField("sales_amount",         DoubleType(),    nullable=False),  # 売上金額
    StructField("sales_quantity",       IntegerType(),   nullable=False),  # 売上数量
    StructField("product_sku",          StringType(),    nullable=False),  # 商品SKU
    StructField("store_id",             StringType(),    nullable=False),  # 店舗ID（外部キー：dim_store.store_id）
])


# ──────────────────────────────────────────────
# 過去1ヶ月分の典型的な取引データを生成（10,000件）
# ──────────────────────────────────────────────

N_TRANSACTIONS = 10_000

fact_rows = []
for i in range(1, N_TRANSACTIONS + 1):
    unit_price = round(random.uniform(3.0, 150.0), 2)
    quantity   = random.randint(1, 5)

    fact_rows.append(Row(
        transaction_id=f"TXN{str(i).zfill(8)}",                 # TXN00000001〜
        transaction_datetime=random_datetime(PERIOD_START, PERIOD_END),
        sales_amount=round(unit_price * quantity, 2),
        sales_quantity=quantity,
        product_sku=random.choice(PRODUCT_SKUS),
        store_id=random.choice(STORE_IDS),
    ))

df_fact_sales = spark.createDataFrame(fact_rows, schema=fact_sales_schema)

print(f"=== fact_sales_transactions（{df_fact_sales.count():,}件） ===")
df_fact_sales.show(10, truncate=False)


# ──────────────────────────────────────────────
# Delta テーブルとして保存（Databricks Free Edition / Hiveメタストア）
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS retail")

(
    df_fact_sales
    .write
    .format("delta")                          # Delta Lake 形式で保存
    .mode("overwrite")                        # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")        # スキーマ変更も上書き許可
    .saveAsTable("retail.fact_sales_transactions")
)

print("retail.fact_sales_transactions の保存が完了しました")
# spark.stop() はここで呼ばない（Databricksのクラスターがセッションを管理するため）
