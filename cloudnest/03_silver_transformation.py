"""
CloudNest Silver レイヤー変換スクリプト（Databricks ノートブック用）
======================================================
Bronze の生データをクレンジング・標準化・整合性検証し、Silver Delta テーブルとして保存する。
Silver層で行う処理：
  1. 主キー重複排除（_ingested_at が最新のレコードを採用）
  2. 文字列トリム／型の標準化
  3. 参照整合性チェック（存在しない customer_id を持つレコードを隔離）
  4. 不正値のフィルタ（負の金額・矛盾した日付など）
  5. 利用ログの週次集計（ダッシュボード・ヘルススコアのトレンド分析用）

本番PoCでは、この層は Lakeflow Declarative Pipelines（旧DLT）の
`@dlt.expect_or_drop` 等のデータ品質エクスペクテーションで宣言的に実装し、
品質メトリクスを Unity Catalog のイベントログで自動収集する想定。

前提：02_bronze_ingestion.py まで実行済みであること
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("CREATE DATABASE IF NOT EXISTS silver")
spark.sql("USE silver")
print("データベース 'silver' を選択しました")

# ──────────────────────────────────────────────
# 0. 有効な customer_id 一覧（参照整合性チェック用）
# ──────────────────────────────────────────────

df_bronze_customers = spark.table("bronze.cloudnest_bronze_customer_master")
valid_customer_ids = df_bronze_customers.select("customer_id").distinct()


def dedupe_by_key(df, key_cols, order_col="_ingested_at"):
    """主キーで重複排除し、最新の取り込みレコードのみ残す"""
    w = Window.partitionBy(*key_cols).orderBy(F.col(order_col).desc())
    return (
        df.withColumn("_rn", F.row_number().over(w))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


# ──────────────────────────────────────────────
# 1. 顧客マスター
# ──────────────────────────────────────────────

df_silver_customers = (
    dedupe_by_key(df_bronze_customers, ["customer_id"])
    .withColumn("company_name", F.trim("company_name"))
    .withColumn("industry", F.trim("industry"))
    .filter(F.col("customer_id").isNotNull())
)
(df_silver_customers.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_customer_master"))
print(f"cloudnest_silver_customer_master 保存完了: {df_silver_customers.count():,} 件")


# ──────────────────────────────────────────────
# 2. 契約データ
# ──────────────────────────────────────────────

df_bronze_contracts = spark.table("bronze.cloudnest_bronze_contracts")
df_silver_contracts = (
    dedupe_by_key(df_bronze_contracts, ["contract_id"])
    .join(valid_customer_ids, "customer_id", "left_semi")  # 参照整合性チェック
    .filter(F.col("arr_usd") > 0)  # 不正値フィルタ（ARRが0以下のレコードを除外）
    .filter(F.col("contract_start_date") <= F.col("contract_end_date"))  # 日付整合性
)
(df_silver_contracts.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_contracts"))
print(f"cloudnest_silver_contracts 保存完了: {df_silver_contracts.count():,} 件")


# ──────────────────────────────────────────────
# 3. プロダクト利用ログ（日次）＋ 週次集計の作成
# ──────────────────────────────────────────────

df_bronze_usage = spark.table("bronze.cloudnest_bronze_usage_logs")
df_silver_usage_daily = (
    df_bronze_usage
    .join(valid_customer_ids, "customer_id", "left_semi")
    .filter(F.col("usage_date").isNotNull())
    .withColumn("daily_active_users", F.greatest(F.col("daily_active_users"), F.lit(0)))
    .dropDuplicates(["customer_id", "usage_date"])
)
(df_silver_usage_daily.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_usage_daily"))
print(f"cloudnest_silver_usage_daily 保存完了: {df_silver_usage_daily.count():,} 件")

# 週次集計（ダッシュボードの「利用率低下トレンド」表示、ヘルススコアの高速化に利用）
df_silver_usage_weekly = (
    df_silver_usage_daily
    .withColumn("week_start", F.date_sub(F.next_day(F.col("usage_date"), "Mon"), 7))
    .groupBy("customer_id", "week_start")
    .agg(
        F.avg("daily_active_users").alias("avg_daily_active_users"),
        F.sum("login_count").alias("weekly_login_count"),
        F.sum("project_created_count").alias("weekly_project_created_count"),
        F.sum("comment_count").alias("weekly_comment_count"),
        F.sum("file_shared_count").alias("weekly_file_shared_count"),
        F.sum("api_call_count").alias("weekly_api_call_count"),
    )
)
(df_silver_usage_weekly.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_usage_weekly"))
print(f"cloudnest_silver_usage_weekly 保存完了: {df_silver_usage_weekly.count():,} 件")


# ──────────────────────────────────────────────
# 4. サポートチケット
# ──────────────────────────────────────────────

df_bronze_tickets = spark.table("bronze.cloudnest_bronze_support_tickets")
df_silver_tickets = (
    dedupe_by_key(df_bronze_tickets, ["ticket_id"])
    .join(valid_customer_ids, "customer_id", "left_semi")
    .withColumn("description", F.trim("description"))
    .filter(F.col("created_date").isNotNull())
)
(df_silver_tickets.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_support_tickets"))
print(f"cloudnest_silver_support_tickets 保存完了: {df_silver_tickets.count():,} 件")


# ──────────────────────────────────────────────
# 5. 請求データ
# ──────────────────────────────────────────────

df_bronze_billing = spark.table("bronze.cloudnest_bronze_billing")
df_silver_billing = (
    dedupe_by_key(df_bronze_billing, ["invoice_id"])
    .join(valid_customer_ids, "customer_id", "left_semi")
    .filter(F.col("amount_usd") >= 0)
)
(df_silver_billing.write.format("delta").mode("overwrite")
 .option("overwriteSchema", "true").saveAsTable("silver.cloudnest_silver_billing"))
print(f"cloudnest_silver_billing 保存完了: {df_silver_billing.count():,} 件")


# ──────────────────────────────────────────────
# 6. データ品質サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== CloudNest Silver レイヤー データ品質サマリー ===")
print("=" * 50)
rejected_contracts = df_bronze_contracts.count() - df_silver_contracts.count()
rejected_tickets = df_bronze_tickets.count() - df_silver_tickets.count()
rejected_billing = df_bronze_billing.count() - df_silver_billing.count()
print(f"  契約データ: 除外 {rejected_contracts} 件（参照整合性/不正値）")
print(f"  サポートチケット: 除外 {rejected_tickets} 件（参照整合性/欠損）")
print(f"  請求データ: 除外 {rejected_billing} 件（参照整合性/不正値）")
print("=" * 50)
