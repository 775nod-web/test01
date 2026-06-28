# Databricks notebook source
# MAGIC %md
# MAGIC # Step2: Bronze Layer — Delta Table 保存
# MAGIC
# MAGIC Step1 で生成した4つの DataFrame に取り込みメタデータを付与し、
# MAGIC `interview_prep` スキーマ配下に Delta Table として保存します。
# MAGIC
# MAGIC **Bronze Layer の原則: 元データの値は一切変更しない。メタデータのみ追加。**
# MAGIC
# MAGIC | Delta Table | 元 DataFrame | ingestion_type |
# MAGIC |---|---|---|
# MAGIC | interview_prep.bronze_pos_transactions | df_pos | streaming |
# MAGIC | interview_prep.bronze_product_master | df_product | batch |
# MAGIC | interview_prep.bronze_store_master | df_store | batch |
# MAGIC | interview_prep.bronze_customer_loyalty | df_customer | batch |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. 前提確認 — Step1 の DataFrame が存在すること

# COMMAND ----------

# Step1（step1_generate_retail_sample_data.py）を同一セッションで実行済みであること。
# df_pos / df_product / df_store / df_customer が定義されていない場合はエラーになります。

for name, df in [("df_pos", df_pos), ("df_product", df_product),
                 ("df_store", df_store), ("df_customer", df_customer)]:
    print(f"{name}: {df.count()} 件")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. スキーマの確認・作成

# COMMAND ----------

spark.sql("CREATE SCHEMA IF NOT EXISTS interview_prep")
print("スキーマ interview_prep を確認しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. メタデータ付与ユーティリティ

# COMMAND ----------

from pyspark.sql import functions as F

def add_bronze_metadata(df, source_name: str, ingestion_type: str):
    """
    Bronze Layer 用の取り込みメタデータ3カラムを付与する。
    元データの値・型・順序は変更しない。
    """
    return (
        df
        .withColumn("source_name",    F.lit(source_name))
        .withColumn("ingestion_type", F.lit(ingestion_type))
        .withColumn("ingested_at",    F.current_timestamp())
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Bronze Delta Table 保存

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3-1. POS取引データ（ニアリアルタイム想定 → streaming）

# COMMAND ----------

bronze_pos = add_bronze_metadata(df_pos, "pos_system", "streaming")

(
    bronze_pos
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("interview_prep.bronze_pos_transactions")
)

print("✓ interview_prep.bronze_pos_transactions を保存しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3-2. 商品マスター（バッチ更新 → batch）

# COMMAND ----------

bronze_product = add_bronze_metadata(df_product, "product_master_system", "batch")

(
    bronze_product
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("interview_prep.bronze_product_master")
)

print("✓ interview_prep.bronze_product_master を保存しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3-3. 店舗マスター（バッチ更新 → batch）

# COMMAND ----------

bronze_store = add_bronze_metadata(df_store, "store_master_system", "batch")

(
    bronze_store
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("interview_prep.bronze_store_master")
)

print("✓ interview_prep.bronze_store_master を保存しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3-4. 顧客ロイヤルティデータ（バッチ更新 → batch）

# COMMAND ----------

bronze_customer = add_bronze_metadata(df_customer, "loyalty_system", "batch")

(
    bronze_customer
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable("interview_prep.bronze_customer_loyalty")
)

print("✓ interview_prep.bronze_customer_loyalty を保存しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. 保存結果の確認

# COMMAND ----------

bronze_tables = [
    ("interview_prep.bronze_pos_transactions", "POS取引データ"),
    ("interview_prep.bronze_product_master",   "商品マスター"),
    ("interview_prep.bronze_store_master",     "店舗マスター"),
    ("interview_prep.bronze_customer_loyalty", "顧客ロイヤルティ"),
]

for table_name, label in bronze_tables:
    df_result = spark.table(table_name)
    cnt = df_result.count()
    print(f"\n=== Bronze: {label}（{table_name}）— {cnt} 件 ===")
    display(df_result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Bronze Layer 保存サマリー

# COMMAND ----------

summary_rows = [
    (table_name, spark.table(table_name).count())
    for table_name, _ in bronze_tables
]

df_summary = spark.createDataFrame(summary_rows, ["table_name", "row_count"])

print("=== Bronze Layer 保存サマリー ===")
display(df_summary)
