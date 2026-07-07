"""
小売メダリオンアーキテクチャ Goldレイヤー 集計チェックスクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_gold_layer_tables.py を同セッションで実行済みで、
      goldスキーマに以下4表が保存されていること
        - gold.daily_sales_kpi
        - gold.store_daily_sales
        - gold.category_daily_sales
        - gold.data_quality_summary

本スクリプトは、Knowledge baseの「#Gold出力」定義に基づき、
gold スキーマの集計結果が silver / bronze から正しく算出されているかを検証する。

検証観点：
  (a) silver.pos_transactions からの再集計値と、保存済みgold表の値が一致するか
      （daily_sales_kpi / store_daily_sales / category_daily_sales）
  (b) 店舗別・カテゴリー別の値を日付単位で合算すると、日次KPIの値と一致するか
      （表間の整合性＝クロスチェック）
  (c) 日次KPIの対象日がsilverの全取引日をカバーしているか（欠落日が無いか）
  (d) gold.data_quality_summary の件数が bronze の生データから再集計した値と一致するか
"""

from pyspark.sql import functions as F

df_pos      = spark.table("silver.pos_transactions")
df_stores   = spark.table("silver.store_master")
df_products = spark.table("silver.product_master")

df_pos_enriched = (
    df_pos
    .withColumn("sales_date", F.to_date("transaction_timestamp"))
    .withColumn("sales_amount", F.col("quantity") * F.col("unit_price"))
    .join(df_stores.select("store_id", "store_name"), on="store_id", how="left")
    .join(df_products.select("product_id", "product_category"), on="product_id", how="left")
)

check_results = []  # (検証項目, 検出件数, 期待値)


# ──────────────────────────────────────────────
# (a) silverからの再集計値とgold保存値の突き合わせ
# ──────────────────────────────────────────────

# --- daily_sales_kpi ---
expected_daily_kpi = (
    df_pos_enriched.groupBy("sales_date")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
    .withColumn("avg_customer_spend", F.round(F.col("total_sales_amount") / F.col("transaction_count"), 2))
)
actual_daily_kpi = spark.table("gold.daily_sales_kpi")
diff_daily_kpi = (
    expected_daily_kpi.exceptAll(actual_daily_kpi).count()
    + actual_daily_kpi.exceptAll(expected_daily_kpi).count()
)
check_results.append(("gold.daily_sales_kpi の再集計値との差分行数", diff_daily_kpi, 0))

# --- store_daily_sales ---
expected_store_sales = (
    df_pos_enriched.groupBy("sales_date", "store_id", "store_name")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.countDistinct("transaction_id").alias("transaction_count"),
        F.sum("quantity").alias("total_quantity"),
    )
)
actual_store_sales = spark.table("gold.store_daily_sales")
diff_store_sales = (
    expected_store_sales.exceptAll(actual_store_sales).count()
    + actual_store_sales.exceptAll(expected_store_sales).count()
)
check_results.append(("gold.store_daily_sales の再集計値との差分行数", diff_store_sales, 0))

# --- category_daily_sales ---
expected_category_sales = (
    df_pos_enriched.groupBy("sales_date", "product_category")
    .agg(
        F.round(F.sum("sales_amount"), 2).alias("total_sales_amount"),
        F.sum("quantity").alias("total_quantity"),
        F.round(F.avg("unit_price"), 2).alias("avg_unit_price"),
    )
)
actual_category_sales = spark.table("gold.category_daily_sales")
diff_category_sales = (
    expected_category_sales.exceptAll(actual_category_sales).count()
    + actual_category_sales.exceptAll(expected_category_sales).count()
)
check_results.append(("gold.category_daily_sales の再集計値との差分行数", diff_category_sales, 0))


# ──────────────────────────────────────────────
# (b) 表間の整合性チェック（店舗別・カテゴリー別を日付で合算→日次KPIと一致するか）
# ──────────────────────────────────────────────

store_rollup = (
    actual_store_sales.groupBy("sales_date")
    .agg(
        F.sum("total_sales_amount").alias("rollup_sales_amount"),
        F.sum("transaction_count").alias("rollup_transaction_count"),
        F.sum("total_quantity").alias("rollup_quantity"),
    )
)
mismatch_store_rollup = (
    actual_daily_kpi.join(store_rollup, on="sales_date", how="inner")
    .filter(
        (F.abs(F.col("total_sales_amount") - F.col("rollup_sales_amount")) > 0.01)
        | (F.col("transaction_count") != F.col("rollup_transaction_count"))
        | (F.col("total_quantity") != F.col("rollup_quantity"))
    )
    .count()
)
check_results.append(("店舗別売上を日付合算した値と日次KPIの不一致日数", mismatch_store_rollup, 0))

category_rollup = (
    actual_category_sales.groupBy("sales_date")
    .agg(
        F.sum("total_sales_amount").alias("rollup_sales_amount"),
        F.sum("total_quantity").alias("rollup_quantity"),
    )
)
mismatch_category_rollup = (
    actual_daily_kpi.join(category_rollup, on="sales_date", how="inner")
    .filter(
        (F.abs(F.col("total_sales_amount") - F.col("rollup_sales_amount")) > 0.01)
        | (F.col("total_quantity") != F.col("rollup_quantity"))
    )
    .count()
)
check_results.append(("カテゴリー別売上を日付合算した値と日次KPIの不一致日数", mismatch_category_rollup, 0))


# ──────────────────────────────────────────────
# (c) 対象日の網羅性チェック（silverの取引日がgoldに欠落していないか）
# ──────────────────────────────────────────────

silver_dates = df_pos_enriched.select("sales_date").distinct()
gold_dates = actual_daily_kpi.select("sales_date").distinct()
missing_dates_in_gold = silver_dates.exceptAll(gold_dates).count()
check_results.append(("silverに存在する取引日でgold.daily_sales_kpiに欠落している日数", missing_dates_in_gold, 0))


# ──────────────────────────────────────────────
# (d) データ品質サマリの再集計チェック（bronzeの生データから再計算）
# ──────────────────────────────────────────────

df_bronze_pos      = spark.table("bronze.pos_transactions")
df_bronze_stores   = spark.table("bronze.store_master")
df_bronze_products = spark.table("bronze.product_master")

valid_store_ids_bronze   = [r.store_id for r in df_bronze_stores.select("store_id").collect()]
valid_product_ids_bronze = [r.product_id for r in df_bronze_products.select("product_id").collect()]

expected_quality_counts = {
    "product_id不一致":     df_bronze_pos.filter(~F.col("product_id").isin(valid_product_ids_bronze)).count(),
    "store_id不一致":       df_bronze_pos.filter(~F.col("store_id").isin(valid_store_ids_bronze)).count(),
    "重複トランザクション":  df_bronze_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).count(),
    "quantity異常":         df_bronze_pos.filter((F.col("quantity") <= 0) | F.col("quantity").isNull()).count(),
    "価格異常":             df_bronze_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0)).count(),
}

actual_quality_rows = {r.quality_issue: r.record_count for r in spark.table("gold.data_quality_summary").collect()}

for issue, expected_count in expected_quality_counts.items():
    actual_count = actual_quality_rows.get(issue)
    check_results.append((f"gold.data_quality_summary[{issue}] の再集計との差分",
                           0 if actual_count == expected_count else abs((actual_count or 0) - expected_count),
                           0))


# ──────────────────────────────────────────────
# 結果表示
# ──────────────────────────────────────────────

print("=" * 90)
print("=== Goldレイヤー 集計チェック結果 ===")
print("=" * 90)

result_rows = []
all_passed = True
for check_name, actual, expected in check_results:
    passed = actual == expected
    all_passed = all_passed and passed
    status = "PASS" if passed else "FAIL"
    result_rows.append((check_name, actual, expected, status))
    print(f"[{status:<4}] {check_name:<55} | 検出値={actual} / 期待値={expected}")

df_check_result = spark.createDataFrame(
    result_rows, ["quality_check", "actual_value", "expected_value", "status"]
)
print("\n--- 集計チェック結果一覧（表形式） ---")
df_check_result.show(truncate=False)

print("=" * 90)
print(f"=== 総合判定: {'全項目 PASS（GoldレイヤーはKnowledge base通りに集計できている）' if all_passed else '一部項目でFAILを検出（要確認）'} ===")
print("=" * 90)
