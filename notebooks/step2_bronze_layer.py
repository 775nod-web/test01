# Databricks notebook source
# MAGIC %md
# MAGIC # Step2: Bronze Layer 構築
# MAGIC
# MAGIC Step1で生成したサンプルデータを **そのまま（無変換）** Delta Table として保存します。
# MAGIC
# MAGIC **保存先スキーマ:** `interview_prep`
# MAGIC
# MAGIC | Delta Table | 元データ |
# MAGIC |---|---|
# MAGIC | `interview_prep.bronze_pos_transactions` | POS取引データ |
# MAGIC | `interview_prep.bronze_product_master`   | 商品マスター |
# MAGIC | `interview_prep.bronze_store_master`     | 店舗マスター |
# MAGIC | `interview_prep.bronze_customer_master`  | 顧客ロイヤルティデータ |

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, DoubleType, DateType, TimestampType
)
from pyspark.sql.functions import current_timestamp, lit
from datetime import date, datetime

spark = SparkSession.builder.getOrCreate()

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Step1 サンプルデータ再生成

# COMMAND ----------

# ---------- 店舗マスター ----------
store_schema = StructType([
    StructField("store_id",   StringType(), False),
    StructField("store_name", StringType(), True),
    StructField("region",     StringType(), True),
    StructField("prefecture", StringType(), True),
])
store_rows = [
    Row(store_id="S001", store_name="東京新宿店", region="関東", prefecture="東京都"),
    Row(store_id="S002", store_name="東京渋谷店", region="関東", prefecture="東京都"),
    Row(store_id="S003", store_name="大阪梅田店", region="関西", prefecture="大阪府"),
    Row(store_id="S004", store_name="名古屋栄店", region="中部", prefecture="愛知県"),
]
df_store = spark.createDataFrame(store_rows, schema=store_schema)

# ---------- 商品マスター ----------
product_schema = StructType([
    StructField("product_id",     StringType(), False),
    StructField("product_name",   StringType(), True),
    StructField("category",       StringType(), True),
    StructField("standard_price", DoubleType(), True),
])
product_rows = [
    Row(product_id="P001", product_name="プレミアムコーヒー", category="飲料", standard_price=580.0),
    Row(product_id="P002", product_name="有機緑茶",           category="飲料", standard_price=420.0),
    Row(product_id="P003", product_name="全粒粉サンドイッチ", category="食品", standard_price=680.0),
    Row(product_id="P004", product_name="プロテインバー",     category="食品", standard_price=320.0),
    Row(product_id="P005", product_name="エコトートバッグ",   category="雑貨", standard_price=1200.0),
]
df_product = spark.createDataFrame(product_rows, schema=product_schema)

# ---------- 顧客マスター ----------
customer_schema = StructType([
    StructField("user_id",       StringType(), False),
    StructField("user_name",     StringType(), True),
    StructField("member_rank",   StringType(), True),
    StructField("registered_at", DateType(),   True),
])
customer_rows = [
    Row(user_id="U001", user_name="田中 太郎", member_rank="Gold",   registered_at=date(2022, 4, 1)),
    Row(user_id="U002", user_name="鈴木 花子", member_rank="Silver", registered_at=date(2023, 1, 15)),
    Row(user_id="U003", user_name="佐藤 次郎", member_rank="Bronze", registered_at=date(2023, 8, 20)),
]
df_customer = spark.createDataFrame(customer_rows, schema=customer_schema)

# ---------- POS取引データ（品質課題含む） ----------
txn_schema = StructType([
    StructField("transaction_id", StringType(),    False),
    StructField("transaction_ts",  TimestampType(), True),
    StructField("store_id",        StringType(),    True),
    StructField("product_id",      StringType(),    True),
    StructField("user_id",         StringType(),    True),
    StructField("quantity",        IntegerType(),   True),
    StructField("unit_price",      DoubleType(),    True),
])
txn_rows = [
    Row(transaction_id="TXN-001", transaction_ts=datetime(2026, 6, 27,  9,  5, 0), store_id="S001", product_id="P001", user_id="U001", quantity=2,  unit_price=580.0),
    Row(transaction_id="TXN-002", transaction_ts=datetime(2026, 6, 27, 10, 15, 0), store_id="S002", product_id="P003", user_id="U002", quantity=1,  unit_price=680.0),
    # ① transaction_id 重複
    Row(transaction_id="TXN-003", transaction_ts=datetime(2026, 6, 27, 11,  0, 0), store_id="S001", product_id="P002", user_id="U001", quantity=3,  unit_price=420.0),
    Row(transaction_id="TXN-003", transaction_ts=datetime(2026, 6, 27, 11,  2, 0), store_id="S001", product_id="P002", user_id="U001", quantity=3,  unit_price=420.0),
    Row(transaction_id="TXN-004", transaction_ts=datetime(2026, 6, 27, 12, 30, 0), store_id="S003", product_id="P004", user_id="U003", quantity=4,  unit_price=320.0),
    Row(transaction_id="TXN-005", transaction_ts=datetime(2026, 6, 27, 13, 45, 0), store_id="S004", product_id="P005", user_id="U002", quantity=1,  unit_price=1200.0),
    # ② store_id 欠損
    Row(transaction_id="TXN-006", transaction_ts=datetime(2026, 6, 27, 14,  0, 0), store_id=None,   product_id="P001", user_id="U001", quantity=1,  unit_price=580.0),
    Row(transaction_id="TXN-007", transaction_ts=datetime(2026, 6, 27, 15, 10, 0), store_id="S002", product_id="P003", user_id="U003", quantity=2,  unit_price=680.0),
    # ③ 商品マスター未存在
    Row(transaction_id="TXN-008", transaction_ts=datetime(2026, 6, 27, 15, 30, 0), store_id="S003", product_id="P999", user_id="U002", quantity=1,  unit_price=500.0),
    Row(transaction_id="TXN-009", transaction_ts=datetime(2026, 6, 27, 16,  0, 0), store_id="S001", product_id="P004", user_id="U001", quantity=5,  unit_price=320.0),
    # ④ user_id 欠損
    Row(transaction_id="TXN-010", transaction_ts=datetime(2026, 6, 27, 16, 20, 0), store_id="S004", product_id="P002", user_id=None,   quantity=2,  unit_price=420.0),
    # ⑤ 顧客マスター未存在
    Row(transaction_id="TXN-011", transaction_ts=datetime(2026, 6, 27, 16, 45, 0), store_id="S002", product_id="P001", user_id="U999", quantity=1,  unit_price=580.0),
    Row(transaction_id="TXN-012", transaction_ts=datetime(2026, 6, 27, 17,  5, 0), store_id="S003", product_id="P005", user_id="U003", quantity=2,  unit_price=1200.0),
    # ⑥ quantity マイナス
    Row(transaction_id="TXN-013", transaction_ts=datetime(2026, 6, 27, 17, 30, 0), store_id="S001", product_id="P003", user_id="U002", quantity=-1, unit_price=680.0),
    Row(transaction_id="TXN-014", transaction_ts=datetime(2026, 6, 27, 18,  0, 0), store_id="S004", product_id="P001", user_id="U001", quantity=3,  unit_price=580.0),
    # ⑦ unit_price NULL
    Row(transaction_id="TXN-015", transaction_ts=datetime(2026, 6, 27, 18, 20, 0), store_id="S002", product_id="P004", user_id="U003", quantity=2,  unit_price=None),
]
df_pos = spark.createDataFrame(txn_rows, schema=txn_schema)

print("サンプルデータ再生成完了")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. 取り込みメタデータ付与ヘルパー関数
# MAGIC
# MAGIC Bronze層では **データを一切変換しない**。メタデータ列のみ追加する。

# COMMAND ----------

def add_ingestion_metadata(df, source_name: str, ingestion_type: str):
    """
    生データに取り込みメタデータ3列を付与して返す。
    データ本体には手を加えない。

    Parameters
    ----------
    source_name    : データソース名 (例: "pos_system", "product_db")
    ingestion_type : "batch" or "streaming"
    """
    return (
        df
        .withColumn("source_name",    lit(source_name))
        .withColumn("ingestion_type", lit(ingestion_type))
        .withColumn("ingested_at",    current_timestamp())
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Bronze Delta Table への保存
# MAGIC
# MAGIC | テーブル | source_name | ingestion_type |
# MAGIC |---|---|---|
# MAGIC | bronze_pos_transactions | pos_system      | streaming |
# MAGIC | bronze_store_master     | store_db        | batch     |
# MAGIC | bronze_product_master   | product_db      | batch     |
# MAGIC | bronze_customer_master  | loyalty_db      | batch     |

# COMMAND ----------

SCHEMA = "interview_prep"

tables = [
    {
        "df":             df_pos,
        "table":          f"{SCHEMA}.bronze_pos_transactions",
        "source_name":    "pos_system",
        "ingestion_type": "streaming",
    },
    {
        "df":             df_store,
        "table":          f"{SCHEMA}.bronze_store_master",
        "source_name":    "store_db",
        "ingestion_type": "batch",
    },
    {
        "df":             df_product,
        "table":          f"{SCHEMA}.bronze_product_master",
        "source_name":    "product_db",
        "ingestion_type": "batch",
    },
    {
        "df":             df_customer,
        "table":          f"{SCHEMA}.bronze_customer_master",
        "source_name":    "loyalty_db",
        "ingestion_type": "batch",
    },
]

for t in tables:
    df_bronze = add_ingestion_metadata(t["df"], t["source_name"], t["ingestion_type"])
    (
        df_bronze
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(t["table"])
    )
    print(f"保存完了: {t['table']}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. 保存結果の確認

# COMMAND ----------

# ---- POS取引データ ----
print("【bronze_pos_transactions】")
df_check_pos = spark.table(f"{SCHEMA}.bronze_pos_transactions")
display(df_check_pos.orderBy("transaction_id", "transaction_ts"))

# COMMAND ----------

print(f"bronze_pos_transactions 件数: {df_check_pos.count()} 件")

# COMMAND ----------

# ---- 店舗マスター ----
print("【bronze_store_master】")
df_check_store = spark.table(f"{SCHEMA}.bronze_store_master")
display(df_check_store.orderBy("store_id"))

# COMMAND ----------

print(f"bronze_store_master 件数: {df_check_store.count()} 件")

# COMMAND ----------

# ---- 商品マスター ----
print("【bronze_product_master】")
df_check_product = spark.table(f"{SCHEMA}.bronze_product_master")
display(df_check_product.orderBy("product_id"))

# COMMAND ----------

print(f"bronze_product_master 件数: {df_check_product.count()} 件")

# COMMAND ----------

# ---- 顧客マスター ----
print("【bronze_customer_master】")
df_check_customer = spark.table(f"{SCHEMA}.bronze_customer_master")
display(df_check_customer.orderBy("user_id"))

# COMMAND ----------

print(f"bronze_customer_master 件数: {df_check_customer.count()} 件")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. 保存テーブルサマリー

# COMMAND ----------

from pyspark.sql.functions import count

summary_rows = [
    Row(
        table_name=t["table"],
        source_name=t["source_name"],
        ingestion_type=t["ingestion_type"],
        row_count=spark.table(t["table"]).count(),
    )
    for t in tables
]

summary_schema = StructType([
    StructField("table_name",     StringType(),  False),
    StructField("source_name",    StringType(),  True),
    StructField("ingestion_type", StringType(),  True),
    StructField("row_count",      IntegerType(), True),
])

df_summary = spark.createDataFrame(summary_rows, schema=summary_schema)

print("【Bronze Layer 保存サマリー】")
display(df_summary)
