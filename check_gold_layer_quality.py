"""
Gold レイヤー 集計検証スクリプト（Databricks Free Edition Notebook 用）

前提: create_gold_layer_tables.py を実行済みで、
      gold.daily_support_kpi / gold.customer_support_risk /
      gold.category_support_summary / gold.data_quality_summary
      が Delta テーブルとして保存されていること。

Knowledge baseで定義されたGold出力要件（日次KPI・顧客単位のリスク分析・
カテゴリ別集計・データ品質サマリ）どおりに集計できているかを、
Silverの元データから独立に再計算し、Goldテーブルの値と突き合わせて検証する。
（Goldテーブル作成コードのロジックをそのまま流用せず、別経路で再計算することで
  集計ロジックの実装ミスを検出できるようにしている）
"""

from pyspark.sql import functions as F

df_silver_tickets = spark.table("silver.support_tickets")
df_silver_customers = spark.table("silver.customer_master")

df_gold_daily_kpi = spark.table("gold.daily_support_kpi")
df_gold_customer_risk = spark.table("gold.customer_support_risk")
df_gold_category_summary = spark.table("gold.category_support_summary")
df_gold_quality_summary = spark.table("gold.data_quality_summary")

UNRESOLVED_STATUSES = ["Open", "In Progress"]
total_silver_tickets = df_silver_tickets.count()

checks = []  # (check_no, check_name, expected, actual, result, description)


def add_check(check_no, name, expected, actual, description):
    result = "PASS" if expected == actual else "FAIL"
    checks.append((check_no, name, str(expected), str(actual), result, description))


# ──────────────────────────────────────────────
# 1. 日次KPI: サポート責任者が見る「全体件数」がSilverの実件数と一致するか
# ──────────────────────────────────────────────
kpi_ticket_total = df_gold_daily_kpi.agg(F.sum("ticket_count")).first()[0]
add_check(1, "日次KPI: チケット総数の整合性", total_silver_tickets, kpi_ticket_total,
          "gold.daily_support_kpiのticket_count合計 = silver.support_tickets全件数")

# ──────────────────────────────────────────────
# 2. 日次KPI: 高優先度件数（Knowledge base定義: priority = High）
# ──────────────────────────────────────────────
silver_high_priority = df_silver_tickets.filter(F.col("priority") == "High").count()
kpi_high_priority_total = df_gold_daily_kpi.agg(F.sum("high_priority_count")).first()[0]
add_check(2, "日次KPI: 高優先度件数の整合性", silver_high_priority, kpi_high_priority_total,
          "gold.daily_support_kpiのhigh_priority_count合計 = priority=Highの実件数")

# ──────────────────────────────────────────────
# 3. 日次KPI: 未解決件数（Knowledge base定義: 未解決 = Open/In Progress）
# ──────────────────────────────────────────────
silver_unresolved = df_silver_tickets.filter(F.col("status").isin(UNRESOLVED_STATUSES)).count()
kpi_unresolved_total = df_gold_daily_kpi.agg(F.sum("unresolved_count")).first()[0]
add_check(3, "日次KPI: 未解決件数の整合性", silver_unresolved, kpi_unresolved_total,
          "gold.daily_support_kpiのunresolved_count合計 = status未解決の実件数")

# ──────────────────────────────────────────────
# 4. 顧客リスク分析: 「顧客単位でサポートリスクを確認できること」
#    （PoCサクセスクライテリア）を満たすため、全顧客を網羅しているか
# ──────────────────────────────────────────────
customer_master_count = df_silver_customers.count()
gold_risk_count = df_gold_customer_risk.count()
add_check(4, "顧客リスク分析: 全顧客の網羅性", customer_master_count, gold_risk_count,
          "gold.customer_support_riskの件数 = silver.customer_masterの全顧客数")

# ──────────────────────────────────────────────
# 5. 顧客リスク分析: 顧客ID不一致・欠損チケットが正しく除外されているか
# ──────────────────────────────────────────────
silver_valid_ticket_count = df_silver_tickets.filter(F.col("is_customer_id_valid")).count()
risk_ticket_total = df_gold_customer_risk.agg(F.sum("ticket_count")).first()[0]
add_check(5, "顧客リスク分析: 有効チケット件数の整合性", silver_valid_ticket_count, risk_ticket_total,
          "gold.customer_support_riskのticket_count合計 = is_customer_id_valid=trueの実件数")

# ──────────────────────────────────────────────
# 6. 顧客リスク分析: risk_level判定ロジックの正確性
#    （高優先度・ネガティブ・未解決のいずれかが3件以上でHigh、1件以上でMedium）
#    を Silver から独立に再計算し、Gold の値と1行ずつ突き合わせる
# ──────────────────────────────────────────────
ticket_agg_recomputed = (
    df_silver_tickets
    .filter(F.col("is_customer_id_valid"))
    .groupBy("customer_id")
    .agg(
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.sum(F.when(F.col("sentiment") == "Negative", 1).otherwise(0)).alias("negative_count"),
        F.sum(F.when(F.col("status").isin(UNRESOLVED_STATUSES), 1).otherwise(0)).alias("unresolved_count"),
    )
)
expected_risk = (
    df_silver_customers.select("customer_id")
    .join(ticket_agg_recomputed, "customer_id", "left")
    .fillna(0, subset=["high_priority_count", "negative_count", "unresolved_count"])
    .withColumn(
        "expected_risk_level",
        F.when(
            (F.col("high_priority_count") >= 3) | (F.col("negative_count") >= 3) | (F.col("unresolved_count") >= 3),
            "High",
        ).when(
            (F.col("high_priority_count") >= 1) | (F.col("negative_count") >= 1) | (F.col("unresolved_count") >= 1),
            "Medium",
        ).otherwise("Low"),
    )
    .select("customer_id", "expected_risk_level")
)
risk_level_mismatch = (
    df_gold_customer_risk.select("customer_id", "risk_level")
    .join(expected_risk, "customer_id")
    .filter(F.col("risk_level") != F.col("expected_risk_level"))
    .count()
)
add_check(6, "顧客リスク分析: risk_levelロジックの正確性", 0, risk_level_mismatch,
          "gold.customer_support_riskのrisk_levelを独立に再計算した結果との不一致件数")

# ──────────────────────────────────────────────
# 7. カテゴリ別集計: カテゴリ欠損分(Unknown)も含めて全件が集計されているか
# ──────────────────────────────────────────────
category_ticket_total = df_gold_category_summary.agg(F.sum("ticket_count")).first()[0]
add_check(7, "カテゴリ別集計: 合計件数の整合性", total_silver_tickets, category_ticket_total,
          "gold.category_support_summaryのticket_count合計 = silver.support_tickets全件数")

# ──────────────────────────────────────────────
# 8. データ品質サマリ: Knowledge base記載の品質課題の種類別件数が
#    Silverのdata_quality_flagsから独立に再計算した値と一致するか
# ──────────────────────────────────────────────
recomputed_quality = (
    df_silver_tickets
    .withColumn("issue_category", F.explode_outer("data_quality_flags"))
    .filter(F.col("issue_category").isNotNull())
    .groupBy("issue_category")
    .agg(F.count("*").alias("expected_affected_count"))
)
quality_summary_mismatch = (
    df_gold_quality_summary.select("issue_category", "affected_count")
    .join(recomputed_quality, "issue_category", "full")
    .filter(
        F.col("affected_count").isNull()
        | F.col("expected_affected_count").isNull()
        | (F.col("affected_count") != F.col("expected_affected_count"))
    )
    .count()
)
add_check(8, "データ品質サマリ: 件数の再計算一致", 0, quality_summary_mismatch,
          "gold.data_quality_summaryのaffected_countをSilverから再計算した値との不一致件数")

# ──────────────────────────────────────────────
# 9. データ品質サマリ: Knowledge baseで挙げられた9種類の品質課題を
#    すべてカバーできているか（顧客ID不一致/欠損、チケットID重複、
#    優先度/ステータス表記揺れ、カテゴリ/センチメントnull、解決時間欠損/異常値、
#    作成日時フォーマット揺れ の合計10カテゴリ ※欠損と異常値を別カテゴリとして計上）
# ──────────────────────────────────────────────
expected_issue_categories = {
    "customer_id_null", "customer_id_unmatched", "ticket_id_duplicate",
    "priority_format_variant", "status_format_variant",
    "category_null", "sentiment_null",
    "resolution_hours_missing", "resolution_hours_outlier",
    "created_at_format_variant",
}
actual_issue_categories = set(
    row.issue_category for row in df_gold_quality_summary.select("issue_category").collect()
)
missing_categories = len(expected_issue_categories - actual_issue_categories)
add_check(9, "データ品質サマリ: 品質課題カテゴリの網羅性", 0, missing_categories,
          "Knowledge base記載の品質課題のうちgold.data_quality_summaryに存在しない件数")


df_check_results = spark.createDataFrame(
    checks, ["check_no", "check_name", "expected", "actual", "result", "description"]
)
print("=== Goldレイヤー 集計検証結果 ===")
display(df_check_results)

all_pass = all(c[4] == "PASS" for c in checks)
print(f"\n総合判定: {'すべてPASS（Knowledge baseどおりに集計できている）' if all_pass else 'FAILあり（要確認）'}")
