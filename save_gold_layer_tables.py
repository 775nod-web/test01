"""
Gold layer 保存スクリプト
- silver スキーマのデータ（customers / transactions）を集計・ルールベースでリスクスコアリングし、
  Knowledge baseで定義された4つのGold出力をテーブルとして保存する
    1. fraud_daily_kpi          : 日次の不正KPI
    2. suspicious_transactions  : 疑わしいトランザクションリスト
    3. customer_risk            : 顧客単位のリスク
    4. data_quality_summary     : データ品質サマリー

リスクスコアリングは短期スコープ「ルールベースで高リスク顧客・高リスク取引を可視化する」
に対応するためのもので、Silverで作成した品質フラグ・特徴量（is_amount_valid等）と
業務ルール（深夜取引・海外取引・高額取引）を組み合わせて0〜100点で算出する。

保存先スキーマ: gold（存在しない場合は自動作成）
  - gold.fraud_daily_kpi
  - gold.suspicious_transactions
  - gold.customer_risk
  - gold.data_quality_summary

前提: save_silver_layer_tables.py が実行済みで bronze / silver 両スキーマに
      テーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F

# Databricks ノートブックでは spark はクラスターから自動注入される

HIGH_RISK_THRESHOLD = 40    # このスコア以上を「高リスク取引」として集計する
SUSPICIOUS_THRESHOLD = 20   # このスコア以上を「疑わしい取引リスト」に掲載する
LARGE_AMOUNT_THRESHOLD = 100000  # 高額取引の閾値（円）
LATE_NIGHT_START_HOUR = 23  # この時刻(23時)以降、または
LATE_NIGHT_END_HOUR = 5     # この時刻(5時)未満を深夜とみなす（23:00〜4:59, JST）


# ──────────────────────────────────────────────
# 0. 保存先スキーマ（gold）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
print("スキーマ 'gold' を作成/選択しました")

# 「深夜取引」「日次集計」等の業務ルールは日本国内向けデジタル銀行の現地時刻（JST）基準のため、
# Sparkセッションのタイムゾーンを明示的に固定する（クラスターのデフォルト設定に依存させない）
spark.conf.set("spark.sql.session.timeZone", "Asia/Tokyo")


# ──────────────────────────────────────────────
# 1. Silver データの読み込みと特徴量の付与
# ──────────────────────────────────────────────

df_tx = spark.table("silver.transactions")
df_cust = spark.table("silver.customers")

df_tx_enriched = (
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


# ──────────────────────────────────────────────
# 2. ルールベースのリスクスコアリング
#    各ルールの条件を満たすたびに加点し、合計を0〜100点に丸める
# ──────────────────────────────────────────────

RULES = [
    # (条件, 加点, 理由テキスト)
    (F.col("fraud_label") == "fraud",     100, "過去調査で不正が確定している取引"),
    (~F.col("is_amount_valid"),            30, "金額が0円またはマイナス"),
    (~F.col("is_customer_valid"),          25, "顧客マスタに存在しない顧客ID"),
    (~F.col("is_account_valid"),           25, "口座マスタに存在しない口座ID"),
    (F.col("is_rapid_succession"),         20, "同一顧客の短時間（15分以内）複数取引"),
    (F.col("is_large_amount"),             15, "高額取引（10万円超）"),
    (F.col("is_overseas"),                 15, "顧客の居住国と異なる国での取引"),
    (~F.col("is_category_valid"),          10, "加盟店カテゴリが不明・未解決"),
    (F.col("is_late_night"),               10, "深夜時間帯（23時〜5時）の取引"),
]

score_expr = F.lit(0)
for condition, points, _ in RULES:
    score_expr = score_expr + F.when(condition, F.lit(points)).otherwise(F.lit(0))

reason_columns = [F.when(condition, F.lit(reason_text)) for condition, _, reason_text in RULES]

df_scored = (
    df_tx_enriched
    .withColumn("risk_score", F.least(score_expr, F.lit(100)))
    .withColumn("risk_reason", F.concat_ws("; ", *reason_columns))
    .withColumn(
        "recommended_action",
        F.when(F.col("risk_score") >= 70, F.lit("即時調査"))
         .when(F.col("risk_score") >= HIGH_RISK_THRESHOLD, F.lit("優先調査"))
         .when(F.col("risk_score") >= SUSPICIOUS_THRESHOLD, F.lit("モニタリング"))
         .otherwise(F.lit("対応不要")),
    )
)


# ──────────────────────────────────────────────
# 3. gold.fraud_daily_kpi（日次の不正KPI）
# ──────────────────────────────────────────────

df_fraud_daily_kpi = (
    df_scored
    .filter(F.col("transaction_timestamp").isNotNull())
    .withColumn("transaction_date", F.to_date("transaction_timestamp"))
    .groupBy("transaction_date")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.sum(F.when(F.col("risk_score") >= HIGH_RISK_THRESHOLD, 1).otherwise(0)).alias("high_risk_transaction_count"),
        F.avg("risk_score").alias("avg_risk_score"),
    )
    .withColumn(
        "suspected_fraud_rate",
        F.round(F.col("high_risk_transaction_count") / F.col("transaction_count"), 4),
    )
    .withColumn("avg_risk_score", F.round(F.col("avg_risk_score"), 2))
    .select(
        "transaction_date", "transaction_count", "total_amount",
        "high_risk_transaction_count", "suspected_fraud_rate", "avg_risk_score",
    )
    .orderBy("transaction_date")
)


# ──────────────────────────────────────────────
# 4. gold.suspicious_transactions（疑わしいトランザクションリスト）
# ──────────────────────────────────────────────

df_suspicious_transactions = (
    df_scored
    .filter(F.col("risk_score") >= SUSPICIOUS_THRESHOLD)
    .select("transaction_id", "customer_id", "amount", "risk_score", "risk_reason", "recommended_action")
    .orderBy(F.col("risk_score").desc(), F.col("transaction_id"))
)


# ──────────────────────────────────────────────
# 5. gold.customer_risk（顧客単位のリスク）
# ──────────────────────────────────────────────

df_customer_risk = (
    df_scored
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("transaction_count"),
        F.sum(F.when(F.col("risk_score") >= HIGH_RISK_THRESHOLD, 1).otherwise(0)).alias("high_risk_transaction_count"),
        F.sum("amount").alias("total_amount"),
        F.max("amount").alias("max_amount"),
        F.sum(F.when(F.col("is_late_night"), 1).otherwise(0)).alias("late_night_transaction_count"),
        F.sum(F.when(F.col("is_overseas"), 1).otherwise(0)).alias("overseas_transaction_count"),
        F.round(F.avg("risk_score"), 2).alias("avg_risk_score"),
        F.first("customer_master_risk_category").alias("customer_master_risk_category"),
    )
    .withColumn(
        "risk_level",
        F.when(F.col("high_risk_transaction_count") >= 2, F.lit("high"))
         .when(F.col("high_risk_transaction_count") == 1, F.lit("medium"))
         .otherwise(F.lit("low")),
    )
    .select(
        "customer_id", "transaction_count", "high_risk_transaction_count", "total_amount",
        "max_amount", "late_night_transaction_count", "overseas_transaction_count",
        "avg_risk_score", "risk_level", "customer_master_risk_category",
    )
    .orderBy(F.col("high_risk_transaction_count").desc())
)


# ──────────────────────────────────────────────
# 6. gold.data_quality_summary（データ品質サマリー）
# ──────────────────────────────────────────────

df_bronze_tx = spark.table("bronze.transactions")

CANONICAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"

quality_counts = {
    "duplicate_transaction_count": df_bronze_tx.count() - df_tx.count(),
    "customer_id_mismatch_count": df_tx.filter(~F.col("is_customer_valid")).count(),
    "account_id_mismatch_count": df_tx.filter(~F.col("is_account_valid")).count(),
    "amount_anomaly_count": df_tx.filter(~F.col("is_amount_valid")).count(),
    "timestamp_format_variant_count": df_bronze_tx.filter(
        ~F.col("transaction_ts").rlike(CANONICAL_TS_PATTERN)
    ).count(),
    "country_code_variant_count": df_bronze_tx.filter(
        F.col("country_code").isNotNull()
        & F.upper(F.trim(F.col("country_code"))).isin("JP", "JAPAN", "JPN")
        & (F.col("country_code") != "JP")
    ).count(),
    "merchant_category_issue_count": df_tx.filter(~F.col("is_category_valid")).count(),
    "fraud_label_null_count": df_tx.filter(F.col("fraud_label").isNull()).count(),
    "rapid_succession_count": df_tx.filter(F.col("is_rapid_succession")).count(),
}

df_data_quality_summary = spark.createDataFrame(
    [tuple(quality_counts.values())], schema=list(quality_counts.keys())
).withColumn("generated_at", F.current_timestamp())


# ──────────────────────────────────────────────
# 7. Delta テーブルとして gold スキーマへ保存
# ──────────────────────────────────────────────

(
    df_fraud_daily_kpi.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("gold.fraud_daily_kpi")
)
(
    df_suspicious_transactions.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("gold.suspicious_transactions")
)
(
    df_customer_risk.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("gold.customer_risk")
)
(
    df_data_quality_summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable("gold.data_quality_summary")
)


# ──────────────────────────────────────────────
# 8. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== Gold layer 保存完了 ===")
print("=" * 60)
print(f"  gold.fraud_daily_kpi         : {spark.table('gold.fraud_daily_kpi').count():>4,} 件")
print(f"  gold.suspicious_transactions : {spark.table('gold.suspicious_transactions').count():>4,} 件")
print(f"  gold.customer_risk           : {spark.table('gold.customer_risk').count():>4,} 件")
print(f"  gold.data_quality_summary    : {spark.table('gold.data_quality_summary').count():>4,} 件")
print("=" * 60)
