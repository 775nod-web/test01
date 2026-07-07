"""
小売メダリオンアーキテクチャ Silverレイヤー 品質チェックスクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_silver_layer_tables.py を同セッションで実行済みで、
      silverスキーマに以下5表が保存されていること
        - silver.store_master
        - silver.product_master
        - silver.member_master
        - silver.pos_transactions            （品質改善後の正データ）
        - silver.pos_transactions_rejected    （品質課題により除外されたデータ）

本スクリプトは、Knowledge baseに定義された8種類の品質課題が
Silverレイヤーの正データ（silver.pos_transactions / silver.product_master）から
正しくクレンジングされているかを検証する。

Gold層（日次売上KPI・店舗別売上・カテゴリー別売上・データ品質サマリ）の
集計に必要な前提条件を満たしているかという観点で検証項目を設計している：
  - store_id / product_id は必ずマスターに存在する（JOINで欠落しない）
  - quantity・unit_priceは集計可能な正の値のみ
  - transaction_timestampは全件パース済み（日次集計が可能）
  - product_categoryはnullが無い（カテゴリー別集計で「未分類」に必ず分類される）
  - customer_idのnullは非会員取引として残存が正しい（エラーではない）
"""

from pyspark.sql import functions as F

df_silver_stores   = spark.table("silver.store_master")
df_silver_products = spark.table("silver.product_master")
df_silver_pos       = spark.table("silver.pos_transactions")
df_silver_pos_rejected = spark.table("silver.pos_transactions_rejected")
df_bronze_pos       = spark.table("bronze.pos_transactions")

valid_store_ids   = [r.store_id for r in df_silver_stores.select("store_id").collect()]
valid_product_ids = [r.product_id for r in df_silver_products.select("product_id").collect()]


# ──────────────────────────────────────────────
# 1. Knowledge baseの品質課題ごとの検証
#    （silver.pos_transactions / silver.product_master に残存していないか）
# ──────────────────────────────────────────────

checks = []  # (品質課題, 対象表, 検出件数, 期待値, 備考)

# (1) product_idがproduct_masterに存在しない
c = df_silver_pos.filter(~F.col("product_id").isin(valid_product_ids)).count()
checks.append(("product_idがproduct_masterに存在しない", "silver.pos_transactions", c, 0))

# (2) store_idがstore_masterに存在しない
c = df_silver_pos.filter(~F.col("store_id").isin(valid_store_ids)).count()
checks.append(("store_idがstore_masterに存在しない", "silver.pos_transactions", c, 0))

# (3) transaction_idの重複
c = df_silver_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).count()
checks.append(("transaction_idの重複", "silver.pos_transactions", c, 0))

# (4) quantityが0または負の値
c = df_silver_pos.filter((F.col("quantity") <= 0) | F.col("quantity").isNull()).count()
checks.append(("quantityが0または負の値", "silver.pos_transactions", c, 0))

# (5) unit_priceがnullまたは負
c = df_silver_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0)).count()
checks.append(("unit_priceがnullまたは負", "silver.pos_transactions", c, 0))

# (6) transaction timestampの形式/timezoneが揺れている（未解析でnullのまま残っていないか）
c = df_silver_pos.filter(F.col("transaction_timestamp").isNull()).count()
checks.append(("transaction_timestampが未解析のまま残存", "silver.pos_transactions", c, 0))

# (7) product_categoryがnullの商品がある
c = df_silver_products.filter(F.col("product_category").isNull()).count()
checks.append(("product_categoryがnullの商品", "silver.product_master", c, 0))

# (8) customer_idがnullの取引（非会員取引として許容するため0件"以外"が正しい＝情報表示）
customer_null_count = df_silver_pos.filter(F.col("customer_id").isNull()).count()
checks.append(("customer_idがnullの取引（非会員取引・意図的に許容）", "silver.pos_transactions", customer_null_count, None))


# ──────────────────────────────────────────────
# 2. Gold集計の前提となるJOIN健全性の検証
#    （isin判定と実際のJOINの両方でマスター不整合が無いことを再確認）
# ──────────────────────────────────────────────

unmatched_store_join = df_silver_pos.join(df_silver_stores, on="store_id", how="left_anti").count()
unmatched_product_join = df_silver_pos.join(df_silver_products, on="product_id", how="left_anti").count()
checks.append(("store_masterとのLEFT ANTI JOIN不一致", "silver.pos_transactions", unmatched_store_join, 0))
checks.append(("product_masterとのLEFT ANTI JOIN不一致", "silver.pos_transactions", unmatched_product_join, 0))


# ──────────────────────────────────────────────
# 3. 件数の整合性検証（データが失われていないか）
# ──────────────────────────────────────────────

bronze_count = df_bronze_pos.count()
silver_valid_count = df_silver_pos.count()
silver_rejected_count = df_silver_pos_rejected.count()
dedup_removed_count = df_bronze_pos.count() - df_bronze_pos.dropDuplicates(["transaction_id"]).count()
reconciled_total = silver_valid_count + silver_rejected_count + dedup_removed_count
checks.append(("Bronze件数とSilver件数(正+却下+重複除去)の整合", "pos_transactions", reconciled_total, bronze_count))


# ──────────────────────────────────────────────
# 4. 検証結果の表示
# ──────────────────────────────────────────────

print("=" * 90)
print("=== Silverレイヤー 品質チェック結果 ===")
print("=" * 90)

result_rows = []
all_passed = True
for issue, table, actual, expected in checks:
    if expected is None:
        status = f"INFO（{actual}件を非会員取引として許容）"
    else:
        passed = actual == expected
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"
    result_rows.append((issue, table, actual, expected, status))
    print(f"[{status:<6}] {issue:<45} | 対象={table:<30} | 検出件数={actual} / 期待値={expected}")

df_check_result = spark.createDataFrame(
    result_rows,
    ["quality_check", "target_table", "detected_count", "expected_count", "status"],
)

print("\n--- 品質チェック結果一覧（表形式） ---")
df_check_result.show(truncate=False)

print("=" * 90)
print(f"=== 総合判定: {'全項目 PASS（Silverレイヤーで品質課題をクレンジング済み）' if all_passed else '一部項目でFAILを検出（要確認）'} ===")
print("=" * 90)
