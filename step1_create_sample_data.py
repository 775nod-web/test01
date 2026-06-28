# =============================================================================
# Step1: サンプルデータ作成 (Medallion Architecture - Retail)
# Databricks Free Edition / PySpark DataFrame API
# =============================================================================

from pyspark.sql import SparkSession
from pyspark.sql import Row
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType,
    DoubleType, TimestampType, DateType
)
from datetime import datetime, date

spark = SparkSession.builder.getOrCreate()

# =============================================================================
# 1. 店舗マスター (store_master)
# =============================================================================
store_schema = StructType([
    StructField("store_id",   StringType(),  False),
    StructField("store_name", StringType(),  True),
    StructField("region",     StringType(),  True),
    StructField("prefecture", StringType(),  True),
])

store_data = [
    ("S001", "新宿店",   "関東", "東京都"),
    ("S002", "渋谷店",   "関東", "東京都"),
    ("S003", "横浜店",   "関東", "神奈川県"),
    ("S004", "大阪梅田店", "関西", "大阪府"),
    ("S005", "京都店",   "関西", "京都府"),
    ("S006", "名古屋店", "中部", "愛知県"),
    ("S007", "福岡店",   "九州", "福岡県"),
]

df_store = spark.createDataFrame(store_data, schema=store_schema)
print("=" * 60)
print("【店舗マスター】")
print("=" * 60)
display(df_store)

# =============================================================================
# 2. 商品マスター (product_master)
# =============================================================================
product_schema = StructType([
    StructField("product_id",       StringType(),  False),
    StructField("product_name",     StringType(),  True),
    StructField("category",         StringType(),  True),
    StructField("sub_category",     StringType(),  True),
    StructField("standard_price",   DoubleType(),  True),
])

product_data = [
    ("P001", "コシヒカリ 5kg",     "食品",   "米・穀物",   1980.0),
    ("P002", "オレンジジュース 1L", "食品",   "飲料",       298.0),
    ("P003", "洗濯洗剤 900g",      "日用品", "洗剤",       598.0),
    ("P004", "シャンプー 400ml",   "日用品", "ヘアケア",   748.0),
    ("P005", "ノートPC 15inch",    "家電",   "PC・タブレット", 89800.0),
    ("P006", "ワイヤレスイヤホン", "家電",   "オーディオ", 12800.0),
    ("P007", "Tシャツ M",          "衣料",   "トップス",   1500.0),
    ("P008", "デニムパンツ 30",    "衣料",   "ボトムス",   4900.0),
    ("P009", "フライパン 26cm",    "キッチン", "調理器具",  3200.0),
    ("P010", "お茶 500ml×24本",   "食品",   "飲料",       1480.0),
]

df_product = spark.createDataFrame(product_data, schema=product_schema)
print("=" * 60)
print("【商品マスター】")
print("=" * 60)
display(df_product)

# =============================================================================
# 3. 顧客マスター (customer_master)
# =============================================================================
customer_schema = StructType([
    StructField("user_id",      StringType(),  False),
    StructField("user_name",    StringType(),  True),
    StructField("member_rank",  StringType(),  True),
    StructField("registered_date", DateType(), True),
])

customer_data = [
    ("U001", "田中 太郎",   "GOLD",   date(2020, 4, 1)),
    ("U002", "鈴木 花子",   "SILVER", date(2021, 6, 15)),
    ("U003", "佐藤 次郎",   "BRONZE", date(2022, 1, 20)),
    ("U004", "伊藤 美咲",   "GOLD",   date(2019, 9, 3)),
    ("U005", "山田 健一",   "SILVER", date(2023, 3, 11)),
    ("U006", "中村 さくら", "BRONZE", date(2023, 11, 5)),
    ("U007", "小林 勇気",   "GOLD",   date(2018, 7, 22)),
    ("U008", "加藤 優子",   "SILVER", date(2022, 8, 30)),
]

df_customer = spark.createDataFrame(customer_data, schema=customer_schema)
print("=" * 60)
print("【顧客マスター (ロイヤルティ)】")
print("=" * 60)
display(df_customer)

# =============================================================================
# 4. POS取引データ (pos_transactions) — データ品質課題を意図的に含む
# =============================================================================
pos_schema = StructType([
    StructField("transaction_id", StringType(),    False),
    StructField("transaction_ts", TimestampType(), True),
    StructField("store_id",       StringType(),    True),
    StructField("user_id",        StringType(),    True),
    StructField("product_id",     StringType(),    True),
    StructField("quantity",       IntegerType(),   True),
    StructField("unit_price",     DoubleType(),    True),
])

pos_data = [
    # ---- 正常データ ----
    ("T001", datetime(2026, 6, 27, 10, 5, 0),  "S001", "U001", "P001",  2,   1980.0),
    ("T002", datetime(2026, 6, 27, 10, 22, 0), "S001", "U002", "P003",  1,   598.0),
    ("T003", datetime(2026, 6, 27, 11, 3, 0),  "S002", "U003", "P010",  3,   1480.0),
    ("T004", datetime(2026, 6, 27, 11, 45, 0), "S002", "U004", "P005",  1,   89800.0),
    ("T005", datetime(2026, 6, 27, 12, 10, 0), "S003", "U005", "P007",  2,   1500.0),
    ("T006", datetime(2026, 6, 27, 12, 33, 0), "S003", "U006", "P008",  1,   4900.0),
    ("T007", datetime(2026, 6, 27, 13, 0, 0),  "S004", "U007", "P006",  1,   12800.0),
    ("T008", datetime(2026, 6, 27, 13, 22, 0), "S004", "U008", "P002",  4,   298.0),
    ("T009", datetime(2026, 6, 27, 14, 5, 0),  "S005", "U001", "P009",  1,   3200.0),
    ("T010", datetime(2026, 6, 27, 14, 40, 0), "S006", "U002", "P004",  2,   748.0),
    ("T011", datetime(2026, 6, 27, 15, 15, 0), "S007", "U003", "P001",  1,   1980.0),
    ("T012", datetime(2026, 6, 27, 15, 50, 0), "S001", "U004", "P010",  6,   1480.0),
    ("T013", datetime(2026, 6, 27, 16, 10, 0), "S002", "U005", "P003",  2,   598.0),
    ("T014", datetime(2026, 6, 27, 16, 35, 0), "S004", "U006", "P007",  3,   1500.0),
    ("T015", datetime(2026, 6, 27, 17, 0, 0),  "S005", "U007", "P002",  5,   298.0),

    # ---- [DQ-1] transaction_id の重複 (T003 が再度登場) ----
    ("T003", datetime(2026, 6, 27, 11, 3, 0),  "S002", "U003", "P010",  3,   1480.0),

    # ---- [DQ-2] store_id が NULL ----
    ("T016", datetime(2026, 6, 27, 17, 30, 0), None,   "U008", "P006",  1,   12800.0),

    # ---- [DQ-3] 商品マスターに存在しない product_id (P999) ----
    ("T017", datetime(2026, 6, 27, 18, 0, 0),  "S001", "U001", "P999",  2,   500.0),

    # ---- [DQ-4] user_id が NULL ----
    ("T018", datetime(2026, 6, 27, 18, 20, 0), "S003", None,   "P008",  1,   4900.0),

    # ---- [DQ-5] 顧客マスターに存在しない user_id (U999) ----
    ("T019", datetime(2026, 6, 27, 18, 45, 0), "S002", "U999", "P003",  1,   598.0),

    # ---- [DQ-6] quantity がマイナス (返品想定外の誤データ) ----
    ("T020", datetime(2026, 6, 27, 19, 10, 0), "S006", "U005", "P001",  -1,  1980.0),

    # ---- [DQ-7] unit_price が NULL ----
    ("T021", datetime(2026, 6, 27, 19, 30, 0), "S007", "U002", "P009",  1,   None),

    # ---- 複合課題: store_id が NULL かつ quantity がマイナス ----
    ("T022", datetime(2026, 6, 27, 20, 0, 0),  None,   "U004", "P010",  -2,  1480.0),
]

df_pos = spark.createDataFrame(pos_data, schema=pos_schema)
print("=" * 60)
print("【POS取引データ (Bronze想定 Raw Data)】")
print("=" * 60)
display(df_pos)

# =============================================================================
# 5. データ品質問題サマリーの表示
# =============================================================================
from pyspark.sql import functions as F

print("=" * 60)
print("【意図的に含めたデータ品質問題一覧】")
print("=" * 60)

# DQ-1: transaction_id の重複
dup_ids = (
    df_pos.groupBy("transaction_id")
          .count()
          .filter(F.col("count") > 1)
          .select("transaction_id")
)
df_dq1 = (
    df_pos.join(dup_ids, on="transaction_id", how="inner")
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-1] transaction_id の重複"))
)

# DQ-2: store_id が NULL
df_dq2 = (
    df_pos.filter(F.col("store_id").isNull())
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-2] store_id が NULL"))
)

# DQ-3: 商品マスターに存在しない product_id
valid_products = df_product.select("product_id")
df_dq3 = (
    df_pos.join(valid_products, on="product_id", how="left_anti")
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-3] 商品マスターに存在しない product_id"))
)

# DQ-4: user_id が NULL
df_dq4 = (
    df_pos.filter(F.col("user_id").isNull())
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-4] user_id が NULL"))
)

# DQ-5: 顧客マスターに存在しない user_id (NULLは除外して検査)
valid_users = df_customer.select("user_id")
df_dq5 = (
    df_pos.filter(F.col("user_id").isNotNull())
          .join(valid_users, on="user_id", how="left_anti")
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-5] 顧客マスターに存在しない user_id"))
)

# DQ-6: quantity がマイナス
df_dq6 = (
    df_pos.filter(F.col("quantity") < 0)
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-6] quantity がマイナス"))
)

# DQ-7: unit_price が NULL
df_dq7 = (
    df_pos.filter(F.col("unit_price").isNull())
          .select("transaction_id", "transaction_ts", "store_id", "product_id")
          .withColumn("dq_issue", F.lit("[DQ-7] unit_price が NULL"))
)

df_dq_summary = (
    df_dq1.union(df_dq2).union(df_dq3).union(df_dq4)
          .union(df_dq5).union(df_dq6).union(df_dq7)
          .orderBy("dq_issue", "transaction_id")
)

display(df_dq_summary)

# 件数サマリー
print("\n--- データ品質問題 件数集計 ---")
display(
    df_dq_summary.groupBy("dq_issue")
                 .agg(F.count("transaction_id").alias("issue_count"))
                 .orderBy("dq_issue")
)
