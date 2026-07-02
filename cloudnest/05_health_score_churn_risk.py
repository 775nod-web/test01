"""
CloudNest ヘルススコア・解約リスク算出スクリプト（Databricks ノートブック用）
======================================================
Customer 360 の特徴量から、説明可能な複合ヘルススコア（0〜100）を算出し、
リスクティア（Healthy / Watch / AtRisk）と ARR at risk を可視化用に出力する。

【スコア設計（課題3「解約リスク判断が経験に依存」への対応）】
  health_score = 0.40 × 利用トレンドスコア
               + 0.25 × サポート体験スコア
               + 0.15 × 請求健全性スコア
               + 0.20 × 更新間近リスク補正（更新90日以内の顧客は利用トレンドの悪化を二重に反映）

  → 各コンポーネントを保持することで「なぜこのスコアなのか」をCSMに説明可能にする（score_breakdown）。
  → risk_tier: health_score >= 75 = Healthy / 50-74 = Watch / < 50 = AtRisk
  → arr_at_risk_usd = arr_usd × リスクティア別の期待値ウェイト（AtRisk:100% / Watch:50% / Healthy:5%）

【週次スナップショット（課題5「経営層が週次でARR at risk等を確認したい」への対応）】
  過去8週分の健全性を Silver テーブルから再計算し、gold_health_score_history に時系列保存する。
  本番PoCでは Databricks Workflows で毎週日曜にこのノートブックをジョブ実行し、
  Lakehouse Monitoring でスコア分布のドリフトも監視する想定。

前提：04_gold_customer_360.py まで実行済みであること
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import date, timedelta

spark.sql("USE gold")

# ──────────────────────────────────────────────
# 0. スコア計算ロジック（共通関数）
#    現在スナップショット（Customer 360）・過去スナップショット双方に適用する
# ──────────────────────────────────────────────

def add_health_score_columns(df):
    """特徴量DataFrameにスコア内訳・health_score・risk_tier・ARR at riskを付与する"""

    df = df.withColumn(
        "usage_trend_score",
        F.when(F.col("usage_trend_pct").isNull(), F.lit(60.0))  # データ不足時は中立値
        .otherwise(F.greatest(F.least(F.lit(50.0) + F.col("usage_trend_pct") * 100, F.lit(100.0)), F.lit(0.0)))
    )

    df = df.withColumn(
        "support_score",
        F.greatest(
            F.lit(100.0)
            - F.least(F.coalesce(F.col("tickets_last_90d"), F.lit(0)) * 5, F.lit(40))
            - (F.coalesce(F.col("avg_ticket_priority_weight"), F.lit(1.0)) - 1) * 10
            - F.when(F.col("avg_csat_last_90d").isNotNull(), (F.lit(5.0) - F.col("avg_csat_last_90d")) * 10).otherwise(F.lit(0.0)),
            F.lit(0.0)
        )
    )

    df = df.withColumn(
        "billing_score",
        F.greatest(
            F.lit(100.0)
            - F.coalesce(F.col("overdue_invoices_last_180d"), F.lit(0)) * 20
            - F.coalesce(F.col("failed_invoices_last_180d"), F.lit(0)) * 15
            - F.coalesce(F.col("downgrades_last_180d"), F.lit(0)) * 25,
            F.lit(0.0)
        )
    )

    df = df.withColumn(
        "near_renewal_flag",
        (F.col("days_to_renewal").isNotNull()) & (F.col("days_to_renewal") >= 0) & (F.col("days_to_renewal") <= 90)
    )
    df = df.withColumn(
        "renewal_proximity_score",
        F.when(F.col("near_renewal_flag"), F.col("usage_trend_score")).otherwise(F.lit(100.0))
    )

    df = df.withColumn(
        "health_score",
        F.round(
            F.col("usage_trend_score") * 0.40
            + F.col("support_score") * 0.25
            + F.col("billing_score") * 0.15
            + F.col("renewal_proximity_score") * 0.20,
            1
        )
    )

    df = df.withColumn(
        "risk_tier",
        F.when(F.col("health_score") >= 75, "Healthy")
        .when(F.col("health_score") >= 50, "Watch")
        .otherwise("AtRisk")
    )

    df = df.withColumn(
        "arr_at_risk_usd",
        F.round(
            F.col("arr_usd") * F.when(F.col("risk_tier") == "AtRisk", F.lit(1.0))
            .when(F.col("risk_tier") == "Watch", F.lit(0.5))
            .otherwise(F.lit(0.05)),
            2
        )
    )

    # 説明可能性：最も足を引っ張っているスコア要因をテキスト化（CSMへの示唆）
    min_component = F.least("usage_trend_score", "support_score", "billing_score")
    df = df.withColumn(
        "top_risk_reason",
        F.when(F.col("risk_tier") == "Healthy", F.lit("特筆すべきリスク要因なし"))
        .when(min_component == F.col("usage_trend_score"), F.lit("プロダクト利用率の低下"))
        .when(min_component == F.col("support_score"), F.lit("サポート問い合わせの増加・重大化"))
        .otherwise(F.lit("支払い遅延・プランダウングレード"))
    )
    df = df.withColumn(
        "top_risk_reason",
        F.when(F.col("near_renewal_flag") & (F.col("risk_tier") != "Healthy"),
               F.concat(F.col("top_risk_reason"), F.lit("（契約更新まで90日以内）")))
        .otherwise(F.col("top_risk_reason"))
    )

    return df


# ──────────────────────────────────────────────
# 1. 現在スナップショット：Customer 360 にスコアを付与
# ──────────────────────────────────────────────

df_customer_360 = spark.table("gold.cloudnest_gold_customer_360")
df_health_latest = add_health_score_columns(df_customer_360).withColumn("as_of_date", F.current_date())

(df_health_latest.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_health_score_latest"))

print(f"=== gold.cloudnest_gold_health_score_latest 保存完了: {df_health_latest.count():,} 件 ===")
df_health_latest.groupBy("risk_tier").agg(
    F.count("*").alias("customer_count"),
    F.round(F.sum("arr_usd"), 0).alias("total_arr_usd"),
    F.round(F.sum("arr_at_risk_usd"), 0).alias("arr_at_risk_usd"),
).orderBy("risk_tier").show(truncate=False)


# ──────────────────────────────────────────────
# 2. 過去スナップショット関数（Silver テーブルから任意時点の特徴量を再計算）
# ──────────────────────────────────────────────

def compute_snapshot_features(as_of_date: date):
    """指定日時点でのCustomer 360相当の特徴量をSilverテーブルから再計算する"""

    as_of_lit = F.lit(as_of_date)

    df_contracts_asof = (
        spark.table("silver.cloudnest_silver_contracts")
        .filter((F.col("contract_start_date") <= as_of_lit) & (F.col("contract_end_date") >= as_of_lit))
        .withColumn("days_to_renewal", F.datediff("contract_end_date", as_of_lit))
        .withColumn("rn", F.row_number().over(Window.partitionBy("customer_id").orderBy(F.col("contract_start_date").desc())))
        .filter(F.col("rn") == 1)
        .select("customer_id", "arr_usd", "licensed_seats", "days_to_renewal")
    )

    df_usage_recent = (
        spark.table("silver.cloudnest_silver_usage_daily")
        .filter((F.col("usage_date") > F.date_sub(as_of_lit, 30)) & (F.col("usage_date") <= as_of_lit))
        .groupBy("customer_id").agg(F.avg("daily_active_users").alias("avg_dau_last_30d"))
    )
    df_usage_prior = (
        spark.table("silver.cloudnest_silver_usage_daily")
        .filter((F.col("usage_date") > F.date_sub(as_of_lit, 60)) & (F.col("usage_date") <= F.date_sub(as_of_lit, 30)))
        .groupBy("customer_id").agg(F.avg("daily_active_users").alias("avg_dau_prior_30d"))
    )
    df_usage = (
        df_usage_recent.join(df_usage_prior, "customer_id", "left")
        .withColumn(
            "usage_trend_pct",
            F.when(F.col("avg_dau_prior_30d").isNull() | (F.col("avg_dau_prior_30d") == 0),
                   F.when(F.col("avg_dau_last_30d") > 0, F.lit(1.0)).otherwise(F.lit(0.0)))
            .otherwise((F.col("avg_dau_last_30d") - F.col("avg_dau_prior_30d")) / F.col("avg_dau_prior_30d"))
        )
    )

    priority_weight = F.when(F.col("priority") == "Critical", 4).when(F.col("priority") == "High", 3) \
        .when(F.col("priority") == "Medium", 2).otherwise(1)
    df_tickets = (
        spark.table("silver.cloudnest_silver_support_tickets")
        .filter((F.col("created_date") > F.date_sub(as_of_lit, 90)) & (F.col("created_date") <= as_of_lit))
        .withColumn("_pw", priority_weight)
        .groupBy("customer_id")
        .agg(F.count("*").alias("tickets_last_90d"),
             F.avg("_pw").alias("avg_ticket_priority_weight"),
             F.avg("csat_score").alias("avg_csat_last_90d"))
    )

    df_billing = (
        spark.table("silver.cloudnest_silver_billing")
        .filter((F.col("billing_date") > F.date_sub(as_of_lit, 180)) & (F.col("billing_date") <= as_of_lit))
        .groupBy("customer_id")
        .agg(F.sum(F.when(F.col("payment_status") == "Overdue", 1).otherwise(0)).alias("overdue_invoices_last_180d"),
             F.sum(F.when(F.col("payment_status") == "Failed", 1).otherwise(0)).alias("failed_invoices_last_180d"),
             F.sum(F.when(F.col("plan_change_type") == "Downgrade", 1).otherwise(0)).alias("downgrades_last_180d"))
    )

    return (
        df_contracts_asof
        .join(df_usage, "customer_id", "left")
        .join(df_tickets, "customer_id", "left")
        .join(df_billing, "customer_id", "left")
        .withColumn("as_of_date", as_of_lit)
    )


# ──────────────────────────────────────────────
# 3. 過去8週分のスナップショットを再計算し、履歴テーブルとして保存
# ──────────────────────────────────────────────

today = date.today()
as_of_dates = sorted({today - timedelta(days=7 * i) for i in range(8)})

history_dfs = []
for d in as_of_dates:
    snap = compute_snapshot_features(d)
    snap_scored = add_health_score_columns(snap)
    history_dfs.append(snap_scored.select(
        "customer_id", "as_of_date", "arr_usd", "days_to_renewal",
        "usage_trend_score", "support_score", "billing_score", "health_score",
        "risk_tier", "arr_at_risk_usd", "top_risk_reason",
    ))

df_health_history = history_dfs[0]
for d in history_dfs[1:]:
    df_health_history = df_health_history.unionByName(d)

(df_health_history.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("gold.cloudnest_gold_health_score_history"))

print(f"\n=== gold.cloudnest_gold_health_score_history 保存完了: {df_health_history.count():,} 件（{len(as_of_dates)}時点 × 顧客数） ===")

print("\n=== 週次 ARR at risk トレンド ===")
df_health_history.groupBy("as_of_date").agg(
    F.round(F.sum("arr_at_risk_usd"), 0).alias("total_arr_at_risk_usd"),
    F.sum(F.when(F.col("risk_tier") == "AtRisk", 1).otherwise(0)).alias("at_risk_customer_count"),
).orderBy("as_of_date").show(truncate=False)

print("\n次のノートブック（06_support_ticket_nlp_analysis.py）でサポートチケットのテキスト分析を行ってください。")
