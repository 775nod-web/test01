"""
Gold レイヤー作成スクリプト（Databricks Free Edition Notebook 用）

前提: create_silver_layer_tables.py を実行済みで、
      silver.customer_master / silver.contract_data / silver.support_tickets
      が Delta テーブルとして保存されていること。

Knowledge baseに定義されたビジネスゴール・KPIに基づき、Silverレイヤーの
データを集計し、以下4種類のGoldテーブルを gold スキーマ（無ければ作成）に
Delta テーブルとして保存する。

  1. gold.daily_support_kpi        : サポートに関する日次KPI
                                      （日次チケット件数・高優先度件数・未解決件数・平均解決時間）
  2. gold.customer_support_risk    : カスタマーサポートのリスク分析
                                      （顧客単位のチケット件数・高優先度件数・ネガティブ件数・
                                        未解決件数・平均解決時間・リスクレベル・推奨アクション）
  3. gold.category_support_summary : カテゴリごとのサポート（カテゴリ別・日別の集計）
  4. gold.data_quality_summary     : データ品質サマリ（品質課題の種類別件数）

顧客単位のリスク分析は、サポート責任者・CSMが「未対応/優先度高/ネガティブ/
未解決チケットを多く抱える顧客」を特定できるようにするための表であるため、
customer_master 全顧客を対象に left join し、チケットが1件もない顧客も
0件として表示されるようにしている。
"""

from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. 保存先スキーマの作成（無ければ作成）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")
print("スキーマ 'gold' を選択しました（存在しない場合は作成済み）")


# ──────────────────────────────────────────────
# Silver テーブルの読み込み
# ──────────────────────────────────────────────

df_customer_master = spark.table("silver.customer_master")
df_support_tickets = spark.table("silver.support_tickets")

UNRESOLVED_STATUSES = ["Open", "In Progress"]
total_ticket_count = df_support_tickets.count()


def save_gold_table(df, table_name: str) -> None:
    (
        df.withColumn("gold_processed_at", F.current_timestamp())
        .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )
    print(f"{table_name} 保存完了: {spark.table(table_name).count()} 件")


# ──────────────────────────────────────────────
# 1. サポートに関する日次KPI
# ──────────────────────────────────────────────

df_daily_support_kpi = (
    df_support_tickets
    .withColumn("ticket_date", F.to_date("created_at"))
    .groupBy("ticket_date")
    .agg(
        F.count("*").alias("ticket_count"),
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.sum(F.when(F.col("status").isin(UNRESOLVED_STATUSES), 1).otherwise(0)).alias("unresolved_count"),
        F.round(F.avg("resolution_hours"), 1).alias("avg_resolution_hours"),
    )
    .orderBy("ticket_date")
)

save_gold_table(df_daily_support_kpi, "gold.daily_support_kpi")


# ──────────────────────────────────────────────
# 2. カスタマーサポートのリスク分析（顧客単位）
# ──────────────────────────────────────────────

df_ticket_agg_by_customer = (
    df_support_tickets
    .filter(F.col("is_customer_id_valid"))  # customer_masterに存在しない/NULLの顧客IDは対象外
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("ticket_count"),
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.sum(F.when(F.col("sentiment") == "Negative", 1).otherwise(0)).alias("negative_count"),
        F.sum(F.when(F.col("status").isin(UNRESOLVED_STATUSES), 1).otherwise(0)).alias("unresolved_count"),
        F.round(F.avg("resolution_hours"), 1).alias("avg_resolution_hours"),
    )
)

df_customer_support_risk = (
    df_customer_master
    .select("customer_id", "company_name", "plan", "arr", "csm_owner", "region")
    .join(df_ticket_agg_by_customer, "customer_id", "left")
    .fillna(0, subset=["ticket_count", "high_priority_count", "negative_count", "unresolved_count"])
    .withColumn(
        "risk_level",
        F.when(
            (F.col("high_priority_count") >= 3) | (F.col("negative_count") >= 3) | (F.col("unresolved_count") >= 3),
            "High",
        ).when(
            (F.col("high_priority_count") >= 1) | (F.col("negative_count") >= 1) | (F.col("unresolved_count") >= 1),
            "Medium",
        ).otherwise("Low"),
    )
    .withColumn(
        "recommended_action",
        F.when(F.col("risk_level") == "High", "CSMによる至急フォローアップが必要")
         .when(F.col("risk_level") == "Medium", "定期的なモニタリングを推奨")
         .otherwise("特段の対応は不要"),
    )
    .orderBy(F.desc("high_priority_count"), F.desc("negative_count"), F.desc("unresolved_count"))
)

save_gold_table(df_customer_support_risk, "gold.customer_support_risk")


# ──────────────────────────────────────────────
# 3. カテゴリごとのサポート（カテゴリ別・日別）
# ──────────────────────────────────────────────

df_category_support_summary = (
    df_support_tickets
    .withColumn("category", F.coalesce(F.col("category"), F.lit("Unknown")))  # 欠損は"Unknown"として集計対象に含める
    .withColumn("ticket_date", F.to_date("created_at"))
    .groupBy("category", "ticket_date")
    .agg(
        F.count("*").alias("ticket_count"),
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.round(F.avg("resolution_hours"), 1).alias("avg_resolution_hours"),
    )
    .orderBy("ticket_date", "category")
)

save_gold_table(df_category_support_summary, "gold.category_support_summary")


# ──────────────────────────────────────────────
# 4. データ品質サマリ（品質課題の種類別件数）
# ──────────────────────────────────────────────

df_data_quality_summary = (
    df_support_tickets
    .withColumn("issue_category", F.explode_outer("data_quality_flags"))
    .filter(F.col("issue_category").isNotNull())
    .groupBy("issue_category")
    .agg(F.count("*").alias("affected_count"))
    .withColumn("total_ticket_count", F.lit(total_ticket_count))
    .withColumn("affected_ratio", F.round(F.col("affected_count") / F.col("total_ticket_count"), 3))
    .orderBy(F.desc("affected_count"))
)

save_gold_table(df_data_quality_summary, "gold.data_quality_summary")


print("\n=== gold スキーマへの保存が完了しました ===")
print("  gold.daily_support_kpi")
print("  gold.customer_support_risk")
print("  gold.category_support_summary")
print("  gold.data_quality_summary")
