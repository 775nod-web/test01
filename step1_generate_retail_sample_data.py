# Databricks notebook source
# MAGIC %md
# MAGIC # Step1: 小売サンプルデータ生成（データ品質課題あり）
# MAGIC
# MAGIC Medallionアーキテクチャ構築の前段として、以下の4テーブルのサンプルデータを生成します。
# MAGIC - `pos_transactions` : POS取引データ（Bronze想定の生データ）
# MAGIC - `product_master`   : 商品マスター
# MAGIC - `store_master`     : 店舗マスター
# MAGIC - `customer_loyalty` : 顧客ロイヤルティデータ
# MAGIC
# MAGIC **意図的にデータ品質課題を埋め込んでいます。**

# COMMAND ----------

from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, DoubleType, DateType
)
from pyspark.sql.functions import col, lit, when
from datetime import date

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 店舗マスター（store_master）

# COMMAND ----------

store_rows = [
    Row(store_id="S001", store_name="新宿店",   region="関東", prefecture="東京都"),
    Row(store_id="S002", store_name="渋谷店",   region="関東", prefecture="東京都"),
    Row(store_id="S003", store_name="梅田店",   region="関西", prefecture="大阪府"),
    Row(store_id="S004", store_name="博多店",   region="九州", prefecture="福岡県"),
]
df_store = spark.createDataFrame(store_rows)

print("=== store_master ===")
display(df_store)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 商品マスター（product_master）

# COMMAND ----------

product_rows = [
    Row(product_id="P001", product_name="Tシャツ",     category="アパレル", base_price=2500.0),
    Row(product_id="P002", product_name="デニムパンツ", category="アパレル", base_price=6800.0),
    Row(product_id="P003", product_name="スニーカー",   category="シューズ", base_price=8900.0),
    Row(product_id="P004", product_name="キャップ",     category="雑貨",     base_price=1800.0),
    Row(product_id="P005", product_name="バッグ",       category="雑貨",     base_price=4500.0),
]
df_product = spark.createDataFrame(product_rows)

print("=== product_master ===")
display(df_product)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 顧客ロイヤルティデータ（customer_loyalty）

# COMMAND ----------

customer_rows = [
    Row(user_id="U001", name="田中 太郎", rank="Gold",   join_date=date(2022, 3, 1)),
    Row(user_id="U002", name="鈴木 花子", rank="Silver", join_date=date(2023, 1, 15)),
    Row(user_id="U003", name="佐藤 次郎", rank="Bronze", join_date=date(2023, 8, 20)),
    Row(user_id="U004", name="山田 美咲", rank="Gold",   join_date=date(2021, 11, 5)),
]
df_customer = spark.createDataFrame(customer_rows)

print("=== customer_loyalty ===")
display(df_customer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. POS取引データ（pos_transactions）
# MAGIC
# MAGIC ### 埋め込んだデータ品質課題
# MAGIC | # | 課題種別 | transaction_id |
# MAGIC |---|---------|----------------|
# MAGIC | 1 | transaction_id 重複 | TXN003 |
# MAGIC | 2 | store_id 欠損 (NULL) | TXN005 |
# MAGIC | 3 | 商品マスター未登録の product_id | TXN007 |
# MAGIC | 4 | user_id 欠損 (NULL) | TXN009 |
# MAGIC | 5 | 顧客マスター未登録の user_id | TXN011 |
# MAGIC | 6 | quantity がマイナス | TXN013 |
# MAGIC | 7 | unit_price が NULL | TXN015 |

# COMMAND ----------

pos_schema = StructType([
    StructField("transaction_id", StringType(),  False),
    StructField("transaction_date",DateType(),   True),
    StructField("store_id",        StringType(), True),
    StructField("product_id",      StringType(), True),
    StructField("user_id",         StringType(), True),
    StructField("quantity",        IntegerType(),True),
    StructField("unit_price",      DoubleType(), True),
])

pos_rows = [
    # ---- 正常データ ----
    Row(transaction_id="TXN001", transaction_date=date(2026,6,25), store_id="S001", product_id="P001", user_id="U001", quantity=2,  unit_price=2500.0),
    Row(transaction_id="TXN002", transaction_date=date(2026,6,25), store_id="S002", product_id="P003", user_id="U002", quantity=1,  unit_price=8900.0),
    # DQ1: transaction_id重複（TXN003が2行）
    Row(transaction_id="TXN003", transaction_date=date(2026,6,25), store_id="S001", product_id="P002", user_id="U003", quantity=1,  unit_price=6800.0),
    Row(transaction_id="TXN003", transaction_date=date(2026,6,25), store_id="S001", product_id="P002", user_id="U003", quantity=1,  unit_price=6800.0),
    Row(transaction_id="TXN004", transaction_date=date(2026,6,26), store_id="S003", product_id="P004", user_id="U004", quantity=3,  unit_price=1800.0),
    # DQ2: store_id 欠損（NULL）
    Row(transaction_id="TXN005", transaction_date=date(2026,6,26), store_id=None,   product_id="P001", user_id="U001", quantity=1,  unit_price=2500.0),
    Row(transaction_id="TXN006", transaction_date=date(2026,6,26), store_id="S004", product_id="P005", user_id="U002", quantity=2,  unit_price=4500.0),
    # DQ3: 商品マスター未登録 product_id="P999"
    Row(transaction_id="TXN007", transaction_date=date(2026,6,26), store_id="S002", product_id="P999", user_id="U003", quantity=1,  unit_price=3000.0),
    Row(transaction_id="TXN008", transaction_date=date(2026,6,27), store_id="S001", product_id="P003", user_id="U004", quantity=1,  unit_price=8900.0),
    # DQ4: user_id 欠損（NULL）
    Row(transaction_id="TXN009", transaction_date=date(2026,6,27), store_id="S003", product_id="P002", user_id=None,   quantity=2,  unit_price=6800.0),
    Row(transaction_id="TXN010", transaction_date=date(2026,6,27), store_id="S004", product_id="P004", user_id="U001", quantity=4,  unit_price=1800.0),
    # DQ5: 顧客マスター未登録 user_id="U999"
    Row(transaction_id="TXN011", transaction_date=date(2026,6,27), store_id="S001", product_id="P005", user_id="U999", quantity=1,  unit_price=4500.0),
    Row(transaction_id="TXN012", transaction_date=date(2026,6,28), store_id="S002", product_id="P001", user_id="U002", quantity=3,  unit_price=2500.0),
    # DQ6: quantity がマイナス
    Row(transaction_id="TXN013", transaction_date=date(2026,6,28), store_id="S003", product_id="P003", user_id="U003", quantity=-1, unit_price=8900.0),
    Row(transaction_id="TXN014", transaction_date=date(2026,6,28), store_id="S004", product_id="P002", user_id="U004", quantity=1,  unit_price=6800.0),
    # DQ7: unit_price が NULL
    Row(transaction_id="TXN015", transaction_date=date(2026,6,28), store_id="S001", product_id="P004", user_id="U001", quantity=2,  unit_price=None),
]

df_pos = spark.createDataFrame(pos_rows, schema=pos_schema)

print(f"=== pos_transactions（{df_pos.count()} 件）===")
display(df_pos)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. データ品質課題サマリー

# COMMAND ----------

# 各DQ課題を検出してフラグ付き1テーブルにまとめる

# DQ1: transaction_id 重複
from pyspark.sql import functions as F

dup_txn = (
    df_pos
    .groupBy("transaction_id")
    .agg(F.count("*").alias("cnt"))
    .filter(col("cnt") > 1)
    .select(col("transaction_id"), lit("DQ1: transaction_id重複").alias("dq_issue"))
)

# DQ2: store_id 欠損
missing_store = (
    df_pos
    .filter(col("store_id").isNull())
    .select(col("transaction_id"), lit("DQ2: store_id欠損(NULL)").alias("dq_issue"))
)

# DQ3: 商品マスター未登録
valid_products = df_product.select("product_id")
unknown_product = (
    df_pos
    .join(valid_products, on="product_id", how="left_anti")
    .select(col("transaction_id"), lit("DQ3: 商品マスター未登録product_id").alias("dq_issue"))
)

# DQ4: user_id 欠損
missing_user = (
    df_pos
    .filter(col("user_id").isNull())
    .select(col("transaction_id"), lit("DQ4: user_id欠損(NULL)").alias("dq_issue"))
)

# DQ5: 顧客マスター未登録（NULLは除外してからanti join）
valid_customers = df_customer.select("user_id")
unknown_user = (
    df_pos
    .filter(col("user_id").isNotNull())
    .join(valid_customers, on="user_id", how="left_anti")
    .select(col("transaction_id"), lit("DQ5: 顧客マスター未登録user_id").alias("dq_issue"))
)

# DQ6: quantity マイナス
neg_qty = (
    df_pos
    .filter(col("quantity") < 0)
    .select(col("transaction_id"), lit("DQ6: quantityがマイナス").alias("dq_issue"))
)

# DQ7: unit_price NULL
null_price = (
    df_pos
    .filter(col("unit_price").isNull())
    .select(col("transaction_id"), lit("DQ7: unit_priceがNULL").alias("dq_issue"))
)

df_dq_summary = (
    dup_txn
    .union(missing_store)
    .union(unknown_product)
    .union(missing_user)
    .union(unknown_user)
    .union(neg_qty)
    .union(null_price)
    .orderBy("transaction_id", "dq_issue")
)

print(f"=== データ品質課題一覧（{df_dq_summary.count()} 件）===")
display(df_dq_summary)
