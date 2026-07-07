# Databricks ノートブック用
# Goldレイヤーの表が、Gold設計（Knowledge baseの「Gold出力」定義）どおりに
# Silverレイヤーのデータを集計できているかを確認する
#
# 前提：silver.silver_* と gold.gold_* の両方が存在すること
#       （save_silver_layer_tables.py と save_gold_layer_tables.py を実行済みであること）

from pyspark.sql import functions as F

CATALOG = spark.catalog.currentCatalog()
SILVER_SCHEMA = f"{CATALOG}.silver"
GOLD_SCHEMA = f"{CATALOG}.gold"

TOLERANCE = 0.01  # 浮動小数点の誤差許容範囲（円）

df_silver_pos = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions")
df_silver_product = spark.table(f"{SILVER_SCHEMA}.silver_product_master")
df_silver_rejected = spark.table(f"{SILVER_SCHEMA}.silver_pos_transactions_rejected")

df_gold_daily = spark.table(f"{GOLD_SCHEMA}.gold_daily_sales_kpi")
df_gold_store = spark.table(f"{GOLD_SCHEMA}.gold_store_daily_sales")
df_gold_category = spark.table(f"{GOLD_SCHEMA}.gold_category_daily_sales")
df_gold_quality = spark.table(f"{GOLD_SCHEMA}.gold_data_quality_summary")

all_passed = True


def check(label: str, passed: bool, detail: str = "") -> None:
    global all_passed
    all_passed = all_passed and passed
    status = "OK" if passed else "NG"
    print(f"  [{status}] {label}{'  ' + detail if detail else ''}")


# ──────────────────────────────────────────────
# 1. 表の列構成が設計どおりかチェック
# ──────────────────────────────────────────────

print("=== 1. Gold表の列構成チェック ===")

EXPECTED_COLUMNS = {
    "gold_daily_sales_kpi": ["sales_date", "total_sales", "transaction_count", "total_quantity", "avg_customer_spend"],
    "gold_store_daily_sales": ["sales_date", "store_id", "store_name", "region", "total_sales", "transaction_count", "total_quantity"],
    "gold_category_daily_sales": ["sales_date", "category", "total_sales", "total_quantity", "avg_unit_price"],
    "gold_data_quality_summary": ["quality_issue", "record_count", "checked_at"],
}
for table_name, expected_cols in EXPECTED_COLUMNS.items():
    actual_cols = spark.table(f"{GOLD_SCHEMA}.{table_name}").columns
    check(f"{table_name} の列構成", actual_cols == expected_cols, f"実際={actual_cols}")


# ──────────────────────────────────────────────
# 2. 売上サマリの整合性チェック（Silver生データとの突合）
#    total_sales / transaction_count / total_quantity が
#    日次・店舗別・カテゴリ別のどの粒度で集計しても一致することを確認する
# ──────────────────────────────────────────────

print("\n=== 2. 売上集計の整合性チェック（Silver突合） ===")

silver_total_sales = df_silver_pos.agg(F.sum("sales_amount")).collect()[0][0] or 0.0
silver_total_qty = df_silver_pos.agg(F.sum("quantity")).collect()[0][0] or 0
silver_txn_count = df_silver_pos.select("transaction_id").distinct().count()

gold_daily_total_sales = df_gold_daily.agg(F.sum("total_sales")).collect()[0][0] or 0.0
gold_daily_total_txn = df_gold_daily.agg(F.sum("transaction_count")).collect()[0][0] or 0
gold_daily_total_qty = df_gold_daily.agg(F.sum("total_quantity")).collect()[0][0] or 0

gold_store_total_sales = df_gold_store.agg(F.sum("total_sales")).collect()[0][0] or 0.0
gold_store_total_txn = df_gold_store.agg(F.sum("transaction_count")).collect()[0][0] or 0
gold_store_total_qty = df_gold_store.agg(F.sum("total_quantity")).collect()[0][0] or 0

gold_category_total_sales = df_gold_category.agg(F.sum("total_sales")).collect()[0][0] or 0.0
gold_category_total_qty = df_gold_category.agg(F.sum("total_quantity")).collect()[0][0] or 0

check("gold_daily_sales_kpi 総売上 = Silver総売上",
      abs(gold_daily_total_sales - silver_total_sales) < TOLERANCE,
      f"gold={gold_daily_total_sales:,.0f} / silver={silver_total_sales:,.0f}")
check("gold_daily_sales_kpi 総取引数 = Silver総取引数",
      gold_daily_total_txn == silver_txn_count,
      f"gold={gold_daily_total_txn:,} / silver={silver_txn_count:,}")
check("gold_daily_sales_kpi 総販売数量 = Silver総販売数量",
      gold_daily_total_qty == silver_total_qty,
      f"gold={gold_daily_total_qty:,} / silver={silver_total_qty:,}")

check("gold_store_daily_sales 総売上 = Silver総売上",
      abs(gold_store_total_sales - silver_total_sales) < TOLERANCE,
      f"gold={gold_store_total_sales:,.0f} / silver={silver_total_sales:,.0f}")
check("gold_store_daily_sales 総取引数 = Silver総取引数",
      gold_store_total_txn == silver_txn_count,
      f"gold={gold_store_total_txn:,} / silver={silver_txn_count:,}")
check("gold_store_daily_sales 総販売数量 = Silver総販売数量",
      gold_store_total_qty == silver_total_qty,
      f"gold={gold_store_total_qty:,} / silver={silver_total_qty:,}")

check("gold_category_daily_sales 総売上 = Silver総売上",
      abs(gold_category_total_sales - silver_total_sales) < TOLERANCE,
      f"gold={gold_category_total_sales:,.0f} / silver={silver_total_sales:,.0f}")
check("gold_category_daily_sales 総販売数量 = Silver総販売数量",
      gold_category_total_qty == silver_total_qty,
      f"gold={gold_category_total_qty:,} / silver={silver_total_qty:,}")


# ──────────────────────────────────────────────
# 3. 集計ロジックの再計算チェック（平均客単価・平均単価）
# ──────────────────────────────────────────────

print("\n=== 3. 平均値ロジックの再計算チェック ===")

df_daily_recalc = (
    df_silver_pos
    .groupBy(F.col("transaction_date").alias("sales_date"))
    .agg(
        F.sum("sales_amount").alias("recalc_total_sales"),
        F.countDistinct("transaction_id").alias("recalc_txn_count"),
    )
    .withColumn("recalc_avg_spend", F.col("recalc_total_sales") / F.col("recalc_txn_count"))
)
df_daily_diff = (
    df_gold_daily.join(df_daily_recalc, on="sales_date", how="inner")
    .withColumn("diff", F.abs(F.col("avg_customer_spend") - F.col("recalc_avg_spend")))
    .filter(F.col("diff") >= TOLERANCE)
)
check("gold_daily_sales_kpi.avg_customer_spend の再計算一致", df_daily_diff.count() == 0)

df_category_recalc = (
    df_silver_pos
    .join(df_silver_product.select("product_id", "category"), on="product_id", how="left")
    .groupBy(F.col("transaction_date").alias("sales_date"), "category")
    .agg(F.avg("unit_price").alias("recalc_avg_price"))
)
df_category_diff = (
    df_gold_category.join(df_category_recalc, on=["sales_date", "category"], how="inner")
    .withColumn("diff", F.abs(F.col("avg_unit_price") - F.col("recalc_avg_price")))
    .filter(F.col("diff") >= TOLERANCE)
)
check("gold_category_daily_sales.avg_unit_price の再計算一致", df_category_diff.count() == 0)

silver_categories = {r.category for r in df_silver_product.select("category").distinct().collect()}
gold_categories = {r.category for r in df_gold_category.select("category").distinct().collect()}
check("「未分類」カテゴリがGoldに反映されている", "未分類" in gold_categories,
      f"gold_categories={sorted(gold_categories)}")
check("Goldのカテゴリ集合がSilver商品マスターのカテゴリ集合に含まれる",
      gold_categories.issubset(silver_categories),
      f"gold={sorted(gold_categories)} / silver={sorted(silver_categories)}")


# ──────────────────────────────────────────────
# 4. データ品質サマリの再計算チェック（Silver隔離データとの突合）
# ──────────────────────────────────────────────

print("\n=== 4. データ品質サマリの再計算チェック ===")

REASON_LABELS = {
    "product_id_not_in_master": "product_idマスター不一致",
    "store_id_not_in_master": "store_idマスター不一致",
    "duplicate_transaction_id": "transaction_id重複",
    "quantity_invalid": "quantity異常",
    "unit_price_invalid": "unit_price異常",
}

df_recalc_quality = (
    df_silver_rejected
    .withColumn("reject_reason", F.explode("reject_reasons"))
    .groupBy("reject_reason")
    .count()
)
recalc_counts = {r.reject_reason: r["count"] for r in df_recalc_quality.collect()}
gold_counts = {r.quality_issue: r.record_count for r in df_gold_quality.collect()}

for reason_key, label in REASON_LABELS.items():
    expected = recalc_counts.get(reason_key, 0)
    actual = gold_counts.get(label, None)
    check(f"品質課題「{label}」の件数一致", actual == expected, f"gold={actual} / silverから再計算={expected}")


# ──────────────────────────────────────────────
# 5. 総合判定
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
if all_passed:
    print("=== 総合判定: OK（Gold設計どおりにSilverデータが集計されています） ===")
else:
    print("=== 総合判定: NG（不一致の項目があります。上記チェック結果を確認してください） ===")
print("=" * 50)
