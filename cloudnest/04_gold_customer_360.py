"""
CloudNest Gold レイヤー：Customer 360 テーブル作成（Databricks ノートブック用）
======================================================
Silver 層の5テーブル（顧客マスター・契約・利用ログ・サポートチケット・請求）を
顧客単位で統合し、Customer Success チーム・経営層・データサイエンスチームが
共通で参照できる「信頼できる唯一の顧客ビュー（Single Source of Truth）」を作成する。

これにより、以下の課題に対応する：
  - 課題1：データが分散し顧客の状態を一元把握できない       → Customer 360 で一元化
  - 課題2：優先対応すべき顧客の共通指標がない                → health_score / risk_tier で標準化
  - 課題3：解約リスク判断が担当者の経験に依存している         → データドリブンな score_breakdown を提供
  - 課題6：解約予測モデルの学習データがない                    → 本テーブルが特徴量ソースになる

前提：03_silver_transformation.py まで実行済みであること
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("CREATE DATABASE IF NOT EXISTS gold")
spark.sql("USE gold")
print("データベース 'gold' を選択しました")

TODAY = F.current_date()

# ──────────────────────────────────────────────
# 0. Silver テーブル読み込み
# ──────────────────────────────────────────────

df_customers = spark.table("silver.cloudnest_silver_customer_master")
df_contracts = spark.table("silver.cloudnest_silver_contracts")
df_usage_daily = spark.table("silver.cloudnest_silver_usage_daily")
df_tickets = spark.table("silver.cloudnest_silver_support_tickets")
df_billing = spark.table("silver.cloudnest_silver_billing")

# ──────────────────────────────────────────────
# 1. 現在アクティブな契約（顧客あたり最新1件）
# ──────────────────────────────────────────────

df_active_contract = (
    df_contracts
    .withColumn("days_to_renewal", F.datediff("contract_end_date", TODAY))
    .withColumn(
        "rn",
        F.row_number().over(
            Window.partitionBy("customer_id").orderBy(F.col("contract_start_date").desc())
        )
    )
    .filter(F.col("rn") == 1)
    .drop("rn")
)

# ──────────────────────────────────────────────
# 2. 利用状況の特徴量（直近30日 vs その前30日でトレンドを算出）
# ──────────────────────────────────────────────

df_usage_recent = (
    df_usage_daily
    .filter(F.col("usage_date") >= F.date_sub(TODAY, 30))
    .groupBy("customer_id")
    .agg(
        F.avg("daily_active_users").alias("avg_dau_last_30d"),
        F.sum("login_count").alias("logins_last_30d"),
        F.sum("project_created_count").alias("projects_created_last_30d"),
        F.sum("comment_count").alias("comments_last_30d"),
        F.sum("file_shared_count").alias("file_shares_last_30d"),
        F.sum("api_call_count").alias("api_calls_last_30d"),
        F.max("usage_date").alias("last_active_date"),
    )
)

df_usage_prior = (
    df_usage_daily
    .filter((F.col("usage_date") >= F.date_sub(TODAY, 60)) & (F.col("usage_date") < F.date_sub(TODAY, 30)))
    .groupBy("customer_id")
    .agg(F.avg("daily_active_users").alias("avg_dau_prior_30d"))
)

df_usage_features = (
    df_usage_recent
    .join(df_usage_prior, "customer_id", "left")
    .withColumn(
        "usage_trend_pct",
        F.when(F.col("avg_dau_prior_30d").isNull() | (F.col("avg_dau_prior_30d") == 0),
               F.when(F.col("avg_dau_last_30d") > 0, F.lit(1.0)).otherwise(F.lit(0.0)))
        .otherwise((F.col("avg_dau_last_30d") - F.col("avg_dau_prior_30d")) / F.col("avg_dau_prior_30d"))
    )
)

# ──────────────────────────────────────────────
# 3. サポートチケットの特徴量（直近90日）
# ──────────────────────────────────────────────

priority_weight = F.when(F.col("priority") == "Critical", 4) \
    .when(F.col("priority") == "High", 3) \
    .when(F.col("priority") == "Medium", 2) \
    .otherwise(1)

df_ticket_features = (
    df_tickets
    .filter(F.col("created_date") >= F.date_sub(TODAY, 90))
    .withColumn("_priority_weight", priority_weight)
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("tickets_last_90d"),
        F.avg("_priority_weight").alias("avg_ticket_priority_weight"),
        F.avg("csat_score").alias("avg_csat_last_90d"),
        F.avg("resolution_hours").alias("avg_resolution_hours_last_90d"),
        F.sum(F.when(F.col("priority").isin("High", "Critical"), 1).otherwise(0)).alias("high_priority_tickets_last_90d"),
    )
)

# ──────────────────────────────────────────────
# 4. 請求の特徴量（直近180日）
# ──────────────────────────────────────────────

df_billing_features = (
    df_billing
    .filter(F.col("billing_date") >= F.date_sub(TODAY, 180))
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("invoices_last_180d"),
        F.sum(F.when(F.col("payment_status") == "Overdue", 1).otherwise(0)).alias("overdue_invoices_last_180d"),
        F.sum(F.when(F.col("payment_status") == "Failed", 1).otherwise(0)).alias("failed_invoices_last_180d"),
        F.sum(F.when(F.col("plan_change_type") == "Downgrade", 1).otherwise(0)).alias("downgrades_last_180d"),
        F.sum(F.when(F.col("plan_change_type") == "Upgrade", 1).otherwise(0)).alias("upgrades_last_180d"),
    )
)

# ──────────────────────────────────────────────
# 5. Customer 360 テーブルの組み立て
# ──────────────────────────────────────────────

df_customer_360 = (
    df_customers
    .join(df_active_contract, "customer_id", "left")
    .join(df_usage_features, "customer_id", "left")
    .join(df_ticket_features, "customer_id", "left")
    .join(df_billing_features, "customer_id", "left")
    .withColumn("seat_utilization_rate",
                F.when(F.col("licensed_seats") > 0, F.col("avg_dau_last_30d") / F.col("licensed_seats")).otherwise(F.lit(None)))
    .withColumn("as_of_date", TODAY)
    .select(
        "customer_id", "company_name", "industry", "employee_band", "region", "csm_owner",
        "signup_date", "is_churned", "churn_date",
        "plan", "arr_usd", "licensed_seats", "contract_status", "auto_renew",
        "contract_start_date", "contract_end_date", "days_to_renewal",
        "avg_dau_last_30d", "avg_dau_prior_30d", "usage_trend_pct", "seat_utilization_rate",
        "logins_last_30d", "projects_created_last_30d", "comments_last_30d",
        "file_shares_last_30d", "api_calls_last_30d", "last_active_date",
        "tickets_last_90d", "avg_ticket_priority_weight", "avg_csat_last_90d",
        "avg_resolution_hours_last_90d", "high_priority_tickets_last_90d",
        "invoices_last_180d", "overdue_invoices_last_180d", "failed_invoices_last_180d",
        "downgrades_last_180d", "upgrades_last_180d",
        "as_of_date",
    )
    # 契約が存在しない（=解約済みで契約履歴のみ、または新規未契約）顧客は現状ビューから除外
    .filter(F.col("contract_status").isNotNull())
)

(df_customer_360.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_customer_360"))

print(f"=== gold.cloudnest_gold_customer_360 保存完了: {df_customer_360.count():,} 件 ===")
df_customer_360.select(
    "customer_id", "company_name", "csm_owner", "arr_usd", "days_to_renewal",
    "usage_trend_pct", "seat_utilization_rate", "tickets_last_90d", "avg_csat_last_90d",
    "overdue_invoices_last_180d",
).show(10, truncate=False)

print("\n次のノートブック（05_health_score_churn_risk.py）でヘルススコア・解約リスクを算出してください。")
