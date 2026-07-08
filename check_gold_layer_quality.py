"""
Gold layer 集計チェックスクリプト
- silver.transactions / silver.customers から Gold の集計ロジックを独立に再計算し、
  保存済みの gold 4表（fraud_daily_kpi / suspicious_transactions / customer_risk /
  data_quality_summary）と突き合わせることで、Knowledge baseに基づく集計が
  正しく行われているかを検証する

前提: save_gold_layer_tables.py が実行済みで bronze / silver / gold 各スキーマに
      テーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F

# Gold保存時と同じ前提（JST基準の深夜判定・日次集計）を再現する
spark.conf.set("spark.sql.session.timeZone", "Asia/Tokyo")

HIGH_RISK_THRESHOLD = 40
SUSPICIOUS_THRESHOLD = 20
LARGE_AMOUNT_THRESHOLD = 100000
LATE_NIGHT_START_HOUR = 23
LATE_NIGHT_END_HOUR = 5

df_tx = spark.table("silver.transactions")
df_cust = spark.table("silver.customers")
df_bronze_tx = spark.table("bronze.transactions")

df_gold_kpi = spark.table("gold.fraud_daily_kpi")
df_gold_suspicious = spark.table("gold.suspicious_transactions")
df_gold_customer_risk = spark.table("gold.customer_risk")
df_gold_dq_summary = spark.table("gold.data_quality_summary")

check_results = []


def record(category, passed, detail=""):
    check_results.append((category, passed))
    print(f"  [{'OK' if passed else 'NG'}] {category}" + (f"  ({detail})" if detail else ""))


# ──────────────────────────────────────────────
# 0. save_gold_layer_tables.py と同一ロジックで期待値（risk_score等）を独立に再計算
#    ※ 保存済みGoldの値と突き合わせることで「集計ロジックの再現性」を検証する
# ──────────────────────────────────────────────

df_enriched = (
    df_tx
    .join(
        df_cust.select(
            "customer_id",
            F.col("residence_country").alias("customer_residence_country"),
            F.col("risk_category").alias("customer_master_risk_category"),
        ),
        on="customer_id", how="left",
    )
    .withColumn("hour_of_day", F.hour("transaction_timestamp"))
    .withColumn(
        "is_late_night",
        F.col("hour_of_day").isNotNull()
        & ((F.col("hour_of_day") >= LATE_NIGHT_START_HOUR) | (F.col("hour_of_day") < LATE_NIGHT_END_HOUR)),
    )
    .withColumn(
        "is_overseas",
        F.col("customer_residence_country").isNotNull()
        & F.col("country_code").isNotNull()
        & (F.col("country_code") != F.col("customer_residence_country")),
    )
    .withColumn("is_large_amount", F.col("amount") > LARGE_AMOUNT_THRESHOLD)
)

RULES = [
    (F.col("fraud_label") == "fraud", 100),
    (~F.col("is_amount_valid"), 30),
    (~F.col("is_customer_valid"), 25),
    (~F.col("is_account_valid"), 25),
    (F.col("is_rapid_succession"), 20),
    (F.col("is_large_amount"), 15),
    (F.col("is_overseas"), 15),
    (~F.col("is_category_valid"), 10),
    (F.col("is_late_night"), 10),
]
score_expr = F.lit(0)
for condition, points in RULES:
    score_expr = score_expr + F.when(condition, F.lit(points)).otherwise(F.lit(0))

df_expected = df_enriched.withColumn("expected_risk_score", F.least(score_expr, F.lit(100)))


# ──────────────────────────────────────────────
# 1. gold.fraud_daily_kpi の再計算チェック
# ──────────────────────────────────────────────

print("=" * 70)
print("(1) gold.fraud_daily_kpi の再計算チェック")
print("=" * 70)

df_expected_kpi = (
    df_expected
    .filter(F.col("transaction_timestamp").isNotNull())
    .withColumn("transaction_date", F.to_date("transaction_timestamp"))
    .groupBy("transaction_date")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.sum(F.when(F.col("expected_risk_score") >= HIGH_RISK_THRESHOLD, 1).otherwise(0)).alias("high_risk_transaction_count"),
        F.round(F.avg("expected_risk_score"), 2).alias("avg_risk_score"),
    )
    .withColumn("suspected_fraud_rate", F.round(F.col("high_risk_transaction_count") / F.col("transaction_count"), 4))
    .select("transaction_date", "transaction_count", "total_amount", "high_risk_transaction_count", "suspected_fraud_rate", "avg_risk_score")
)

diff_kpi = df_gold_kpi.exceptAll(df_expected_kpi).count() + df_expected_kpi.exceptAll(df_gold_kpi).count()
print(f"  Gold保存値 と 再計算値 の差分行数 : {diff_kpi}")
record("fraud_daily_kpi の再計算一致", diff_kpi == 0)

expected_dates = df_expected.filter(F.col("transaction_timestamp").isNotNull()).select(
    F.to_date("transaction_timestamp").alias("d")
).distinct().count()
gold_dates = df_gold_kpi.select("transaction_date").distinct().count()
print(f"  Silverに存在する取引日数 : {expected_dates} / gold.fraud_daily_kpiの日数 : {gold_dates}")
record("fraud_daily_kpi の日付網羅性（全取引日が集計に含まれる）", expected_dates == gold_dates)


# ──────────────────────────────────────────────
# 2. gold.suspicious_transactions の再計算チェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(2) gold.suspicious_transactions の再計算チェック")
print("=" * 70)

df_expected_suspicious_ids = (
    df_expected.filter(F.col("expected_risk_score") >= SUSPICIOUS_THRESHOLD).select("transaction_id")
)
missing_from_list = df_expected_suspicious_ids.exceptAll(df_gold_suspicious.select("transaction_id")).count()
extra_in_list = df_gold_suspicious.select("transaction_id").exceptAll(df_expected_suspicious_ids).count()
print(f"  閾値({SUSPICIOUS_THRESHOLD}点)以上なのにリスト未掲載 : {missing_from_list}件")
print(f"  閾値未満なのにリストに誤掲載             : {extra_in_list}件")
record("suspicious_transactions の網羅性・正確性（閾値通りに過不足なく抽出）", missing_from_list == 0 and extra_in_list == 0)

empty_reason_count = df_gold_suspicious.filter(
    F.col("risk_reason").isNull() | (F.trim(F.col("risk_reason")) == "")
).count()
print(f"  risk_reasonが空のレコード数（理由が無い＝説明責任を果たせない） : {empty_reason_count}件")
record("suspicious_transactions は全件リスク理由を保持している", empty_reason_count == 0)

expected_action = (
    F.when(F.col("risk_score") >= 70, F.lit("即時調査"))
     .when(F.col("risk_score") >= HIGH_RISK_THRESHOLD, F.lit("優先調査"))
     .when(F.col("risk_score") >= SUSPICIOUS_THRESHOLD, F.lit("モニタリング"))
     .otherwise(F.lit("対応不要"))
)
action_mismatch = df_gold_suspicious.withColumn("expected_action", expected_action).filter(
    F.col("recommended_action") != F.col("expected_action")
).count()
print(f"  risk_scoreと recommended_action の対応が不整合な件数 : {action_mismatch}件")
record("suspicious_transactions の recommended_action がスコア基準と整合", action_mismatch == 0)


# ──────────────────────────────────────────────
# 3. gold.customer_risk の再計算チェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(3) gold.customer_risk の再計算チェック")
print("=" * 70)

df_expected_customer_risk = (
    df_expected
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum(F.when(F.col("expected_risk_score") >= HIGH_RISK_THRESHOLD, 1).otherwise(0)).alias("high_risk_transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.max("amount").alias("max_amount"),
        F.sum(F.when(F.col("is_late_night"), 1).otherwise(0)).alias("late_night_transaction_count"),
        F.sum(F.when(F.col("is_overseas"), 1).otherwise(0)).alias("overseas_transaction_count"),
    )
)

diff_customer_risk = (
    df_gold_customer_risk.select(
        "customer_id", "transaction_count", "high_risk_transaction_count",
        "total_amount", "max_amount", "late_night_transaction_count", "overseas_transaction_count",
    ).exceptAll(df_expected_customer_risk).count()
    + df_expected_customer_risk.exceptAll(
        df_gold_customer_risk.select(
            "customer_id", "transaction_count", "high_risk_transaction_count",
            "total_amount", "max_amount", "late_night_transaction_count", "overseas_transaction_count",
        )
    ).count()
)
print(f"  Gold保存値 と 再計算値 の差分行数 : {diff_customer_risk}")
record("customer_risk の集計一致（件数/金額/深夜/海外）", diff_customer_risk == 0)

expected_customers = df_tx.select("customer_id").distinct().count()
gold_customers = df_gold_customer_risk.select("customer_id").distinct().count()
print(f"  Silverの取引に登場する顧客数（マスタ不一致含む） : {expected_customers} / gold.customer_riskの顧客数 : {gold_customers}")
record("customer_risk の網羅性（マスタ不一致の顧客も含め全顧客が集計対象）", expected_customers == gold_customers)

risk_level_mismatch = df_gold_customer_risk.withColumn(
    "expected_risk_level",
    F.when(F.col("high_risk_transaction_count") >= 2, F.lit("high"))
     .when(F.col("high_risk_transaction_count") == 1, F.lit("medium"))
     .otherwise(F.lit("low")),
).filter(F.col("risk_level") != F.col("expected_risk_level")).count()
print(f"  risk_level が high_risk_transaction_count と不整合な件数 : {risk_level_mismatch}件")
record("customer_risk の risk_level が基準どおり", risk_level_mismatch == 0)


# ──────────────────────────────────────────────
# 4. gold.data_quality_summary の再計算チェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(4) gold.data_quality_summary の再計算チェック")
print("=" * 70)

CANONICAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"

expected_quality_counts = {
    "duplicate_transaction_count": df_bronze_tx.count() - df_tx.count(),
    "customer_id_mismatch_count": df_tx.filter(~F.col("is_customer_valid")).count(),
    "account_id_mismatch_count": df_tx.filter(~F.col("is_account_valid")).count(),
    "amount_anomaly_count": df_tx.filter(~F.col("is_amount_valid")).count(),
    "timestamp_format_variant_count": df_bronze_tx.filter(~F.col("transaction_ts").rlike(CANONICAL_TS_PATTERN)).count(),
    "country_code_variant_count": df_bronze_tx.filter(
        F.col("country_code").isNotNull()
        & F.upper(F.trim(F.col("country_code"))).isin("JP", "JAPAN", "JPN")
        & (F.col("country_code") != "JP")
    ).count(),
    "merchant_category_issue_count": df_tx.filter(~F.col("is_category_valid")).count(),
    "fraud_label_null_count": df_tx.filter(F.col("fraud_label").isNull()).count(),
    "rapid_succession_count": df_tx.filter(F.col("is_rapid_succession")).count(),
}

gold_dq_row = df_gold_dq_summary.select(*expected_quality_counts.keys()).collect()[0].asDict()

print(f"  {'指標':38s}{'Gold保存値':>10s}{'再計算値':>10s}  判定")
all_dq_match = True
for metric, expected_value in expected_quality_counts.items():
    actual_value = gold_dq_row[metric]
    match = actual_value == expected_value
    all_dq_match = all_dq_match and match
    print(f"  {metric:38s}{actual_value:>10}{expected_value:>10}  {'OK' if match else 'NG'}")
record("data_quality_summary の全指標が再計算値と一致", all_dq_match)


# ──────────────────────────────────────────────
# 総合結果
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("Gold layer 集計チェック 総合結果")
print("=" * 70)
for category, passed in check_results:
    print(f"  [{'PASS' if passed else 'FAIL'}] {category}")

overall_passed = all(passed for _, passed in check_results)
print("=" * 70)
print(f"最終判定: {'全項目 PASS（Gold layerの集計はKnowledge baseに沿って正しく行われている）' if overall_passed else '一部 FAIL（要確認）'}")
print("=" * 70)
