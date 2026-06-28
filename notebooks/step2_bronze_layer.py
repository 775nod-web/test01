# Databricks notebook source
# MAGIC %md
# MAGIC # Step2: Bronze Layer 構築
# MAGIC
# MAGIC Step1で生成済みのDataFrame（df_pos / df_store / df_product / df_customer）を
# MAGIC **そのまま（無変換）** Delta Table として `interview_prep` スキーマに保存します。
# MAGIC
# MAGIC | Delta Table | 元DataFrame | ingestion_type |
# MAGIC |---|---|---|
# MAGIC | `interview_prep.bronze_pos`      | df_pos      | streaming |
# MAGIC | `interview_prep.bronze_store`    | df_store    | batch     |
# MAGIC | `interview_prep.bronze_product`  | df_product  | batch     |
# MAGIC | `interview_prep.bronze_customer` | df_customer | batch     |

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. 取り込みメタデータ付与ヘルパー関数

# COMMAND ----------

from pyspark.sql.functions import current_timestamp, lit

def add_ingestion_metadata(df, source_name: str, ingestion_type: str):
    """データ本体には手を加えず、取り込みメタデータ3列のみ付与する。"""
    return (
        df
        .withColumn("source_name",    lit(source_name))
        .withColumn("ingestion_type", lit(ingestion_type))
        .withColumn("ingested_at",    current_timestamp())
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Bronze Delta Table への保存

# COMMAND ----------

SCHEMA = "interview_prep"

tables = [
    {"df": df_pos,      "table": f"{SCHEMA}.bronze_pos",      "source_name": "pos_system",  "ingestion_type": "streaming"},
    {"df": df_store,    "table": f"{SCHEMA}.bronze_store",    "source_name": "store_db",    "ingestion_type": "batch"},
    {"df": df_product,  "table": f"{SCHEMA}.bronze_product",  "source_name": "product_db",  "ingestion_type": "batch"},
    {"df": df_customer, "table": f"{SCHEMA}.bronze_customer", "source_name": "loyalty_db",  "ingestion_type": "batch"},
]

for t in tables:
    (
        add_ingestion_metadata(t["df"], t["source_name"], t["ingestion_type"])
        .write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(t["table"])
    )
    print(f"保存完了: {t['table']}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. 保存結果の確認

# COMMAND ----------

print("【bronze_pos】")
display(spark.table(f"{SCHEMA}.bronze_pos").orderBy("transaction_id", "transaction_ts"))

# COMMAND ----------

print("【bronze_store】")
display(spark.table(f"{SCHEMA}.bronze_store").orderBy("store_id"))

# COMMAND ----------

print("【bronze_product】")
display(spark.table(f"{SCHEMA}.bronze_product").orderBy("product_id"))

# COMMAND ----------

print("【bronze_customer】")
display(spark.table(f"{SCHEMA}.bronze_customer").orderBy("user_id"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. 保存テーブルサマリー

# COMMAND ----------

from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

summary_rows = [
    Row(table_name=t["table"], source_name=t["source_name"], ingestion_type=t["ingestion_type"],
        row_count=spark.table(t["table"]).count())
    for t in tables
]

df_summary = spark.createDataFrame(
    summary_rows,
    schema=StructType([
        StructField("table_name",     StringType(),  False),
        StructField("source_name",    StringType(),  True),
        StructField("ingestion_type", StringType(),  True),
        StructField("row_count",      IntegerType(), True),
    ])
)

print("【Bronze Layer 保存サマリー】")
display(df_summary)
