"""
カスタマーサポート チケット分析 PoC - サンプルデータ確認・品質レポート表示スクリプト
（Databricks Free Edition Notebook 用）

前提: generate_and_save_sample_data.py を実行済みで、
      sample.customer_master / sample.contract_data / sample.support_tickets
      が Delta テーブルとして保存されていること。

このスクリプトは以下を表示する。
  1. 各表のサンプルデータ
  2. 各表の件数
  3. 品質課題データの件数
  4. 意図的に含めた品質課題一覧（何を・何件含めたか）
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ──────────────────────────────────────────────
# 0. sample スキーマのテーブル読み込み
# ──────────────────────────────────────────────

df_customer_master = spark.table("sample.customer_master")
df_contract_data = spark.table("sample.contract_data")
df_support_tickets = spark.table("sample.support_tickets")

print("=== sample スキーマのテーブル一覧 ===")
spark.sql("SHOW TABLES IN sample").show(truncate=False)


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ・件数
# ──────────────────────────────────────────────

print(f"\n=== customer_master（全 {df_customer_master.count()} 件） ===")
display(df_customer_master)  # Databricksノートブックの display() で表形式表示

print(f"\n=== contract_data（全 {df_contract_data.count()} 件） ===")
display(df_contract_data)

total_tickets = df_support_tickets.count()
print(f"\n=== support_tickets（全 {total_tickets} 件） ===")
display(df_support_tickets)

# 表ごとの件数サマリ
table_record_counts = spark.createDataFrame(
    [
        ("customer_master", df_customer_master.count()),
        ("contract_data", df_contract_data.count()),
        ("support_tickets", total_tickets),
    ],
    ["table_name", "record_count"],
)
print("\n=== 各表の件数サマリ ===")
display(table_record_counts)


# ──────────────────────────────────────────────
# 2. 品質課題の判定（フラグ列を付与）
#    ※ 各フラグは generate_and_save_sample_data.py で意図的に埋め込んだ
#      品質課題の定義と対応している
# ──────────────────────────────────────────────

VALID_CUSTOMER_IDS = [r.customer_id for r in df_customer_master.select("customer_id").collect()]
PRIORITIES_CANONICAL = ["Low", "Medium", "High"]
STATUSES_CANONICAL = ["Open", "In Progress", "Resolved", "Closed"]
RESOLVED_LIKE = ["Resolved", "Closed", "resolved", "close"]

ticket_id_window = Window.partitionBy("ticket_id")

df_flagged = (
    df_support_tickets
    .withColumn(
        "flag_customer_unmatched",
        F.col("customer_id").isNotNull() & (~F.col("customer_id").isin(VALID_CUSTOMER_IDS)),
    )
    .withColumn("flag_customer_null", F.col("customer_id").isNull())
    .withColumn("flag_ticket_id_duplicate", F.count("*").over(ticket_id_window) > 1)
    .withColumn(
        "flag_priority_variant",
        F.col("priority").isNotNull() & (~F.col("priority").isin(PRIORITIES_CANONICAL)),
    )
    .withColumn(
        "flag_status_variant",
        F.col("status").isNotNull() & (~F.col("status").isin(STATUSES_CANONICAL)),
    )
    .withColumn("flag_category_null", F.col("category").isNull())
    .withColumn("flag_sentiment_null", F.col("sentiment").isNull())
    .withColumn(
        "flag_resolution_null",
        F.col("status").isin(RESOLVED_LIKE) & F.col("resolution_hours").isNull(),
    )
    .withColumn(
        "flag_resolution_outlier",
        F.col("status").isin(RESOLVED_LIKE)
        & F.col("resolution_hours").isNotNull()
        & (F.col("resolution_hours") > 720),
    )
    .withColumn(
        "flag_created_at_variant",
        ~F.col("created_at").rlike(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"),
    )
)

FLAG_COLUMNS = [
    "flag_customer_unmatched", "flag_customer_null", "flag_ticket_id_duplicate",
    "flag_priority_variant", "flag_status_variant", "flag_category_null",
    "flag_sentiment_null", "flag_resolution_null", "flag_resolution_outlier",
    "flag_created_at_variant",
]

df_flagged = df_flagged.withColumn(
    "has_quality_issue",
    F.array_contains(F.array(*[F.col(c) for c in FLAG_COLUMNS]), True),
)


# ──────────────────────────────────────────────
# 3. 品質課題データの件数
# ──────────────────────────────────────────────

quality_affected_count = df_flagged.filter(F.col("has_quality_issue")).count()
print(f"\n=== 品質課題データの件数 ===")
print(f"support_tickets 全 {total_tickets} 件中、品質課題を含むレコード: {quality_affected_count} 件"
      f"（{quality_affected_count / total_tickets:.1%}）")


# ──────────────────────────────────────────────
# 4. 意図的に含めた品質課題一覧
# ──────────────────────────────────────────────

ISSUE_DEFINITIONS = [
    ("flag_customer_unmatched",  "顧客マスター不一致",           "customer_masterに存在しないcustomer_idを持つチケット"),
    ("flag_customer_null",       "顧客ID欠損",                   "customer_id が NULL"),
    ("flag_ticket_id_duplicate", "チケットID重複",               "同一ticket_idが複数行に存在（重複取り込みを想定）"),
    ("flag_priority_variant",    "優先度の表記揺れ",             "priorityが正規値(Low/Medium/High)以外の表記（例: high/HIGH/urget/urgent）"),
    ("flag_status_variant",      "ステータスの表記揺れ",         "statusが正規値(Open/In Progress/Resolved/Closed)以外の表記（例: open/inprogress/resolved/close）"),
    ("flag_category_null",       "カテゴリ欠損",                 "category が NULL"),
    ("flag_sentiment_null",      "センチメント欠損",             "sentiment が NULL"),
    ("flag_resolution_null",     "解決時間欠損（異常）",         "ステータスが解決済み(Resolved/Closed相当)なのに resolution_hours が NULL"),
    ("flag_resolution_outlier",  "解決時間の異常値",             "resolution_hours が 720時間（30日）を超える極端な値"),
    ("flag_created_at_variant",  "作成日時のフォーマット揺れ",   "created_at が正規フォーマット 'YYYY-MM-DD HH:MM:SS' 以外（例: '/', ISO8601等）"),
]

quality_issue_summary_rows = [
    (i, name, df_flagged.filter(F.col(flag_col)).count(), desc)
    for i, (flag_col, name, desc) in enumerate(ISSUE_DEFINITIONS, start=1)
]

df_quality_issue_summary = spark.createDataFrame(
    quality_issue_summary_rows,
    ["issue_no", "issue_category", "affected_count", "description"],
)

print("\n=== 意図的に含めた品質課題一覧 ===")
display(df_quality_issue_summary)

total_by_category = sum(row[2] for row in quality_issue_summary_rows)
print(f"品質課題カテゴリ別件数の合計: {total_by_category} 件"
      f"（重複なしの実件数 {quality_affected_count} 件と一致することを確認）")


# ──────────────────────────────────────────────
# 5. （参考）品質課題を含むレコードの実データ
# ──────────────────────────────────────────────

print("\n=== （参考）品質課題を含むチケットの実データ ===")
display(
    df_flagged.filter(F.col("has_quality_issue"))
    .select("ticket_id", "customer_id", "created_at", "priority", "status",
            "category", "sentiment", "resolution_hours", *FLAG_COLUMNS)
    .orderBy("ticket_id")
)
