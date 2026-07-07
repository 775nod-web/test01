"""
Silver レイヤー 品質チェックスクリプト（Databricks Free Edition Notebook 用）

前提: create_silver_layer_tables.py を実行済みで、
      silver.customer_master / silver.contract_data / silver.support_tickets
      が Delta テーブルとして保存されていること。

Knowledge baseに記載された9種類の品質課題ごとに、Silverレイヤーで
意図通りクレンジングされているか（直せるものは直っているか、直すべきでない
ものは正しくフラグ管理されたままNULLを保持しているか）を検証する。

さらに、Gold層で計画している4つの集計（日次KPI／顧客リスク分析／
カテゴリ別集計／データ品質サマリ）が、Silverのスキーマ・データで
実際に算出可能かどうかも実行して確認する。
"""

from pyspark.sql import functions as F

df_customer_master = spark.table("silver.customer_master")
df_contract_data = spark.table("silver.contract_data")
df_support_tickets = spark.table("silver.support_tickets")

PRIORITIES_CANONICAL = ["Low", "Medium", "High"]
STATUSES_CANONICAL = ["Open", "In Progress", "Resolved", "Closed"]
UNRESOLVED_STATUSES = ["Open", "In Progress"]
RESOLUTION_HOURS_MAX = 720.0  # 30日。create_silver_layer_tables.py と同じ閾値

total_tickets = df_support_tickets.count()

checks = []  # (check_no, check_name, expected, actual, result, description)


def add_check(check_no, name, expected, actual, description):
    result = "PASS" if actual == expected else "FAIL"
    checks.append((check_no, name, str(expected), str(actual), result, description))


# ──────────────────────────────────────────────
# 1. 優先度の表記揺れが正規値に解消されているか
# ──────────────────────────────────────────────
priority_variant_remaining = df_support_tickets.filter(
    ~F.col("priority").isin(PRIORITIES_CANONICAL)
).count()
add_check(1, "優先度の表記揺れ解消", 0, priority_variant_remaining,
          "priorityがLow/Medium/High以外の残存件数")

# ──────────────────────────────────────────────
# 2. ステータスの表記揺れが正規値に解消されているか
# ──────────────────────────────────────────────
status_variant_remaining = df_support_tickets.filter(
    ~F.col("status").isin(STATUSES_CANONICAL)
).count()
add_check(2, "ステータスの表記揺れ解消", 0, status_variant_remaining,
          "statusがOpen/In Progress/Resolved/Closed以外の残存件数")

# ──────────────────────────────────────────────
# 3. チケットID重複が解消されているか
# ──────────────────────────────────────────────
distinct_ticket_ids = df_support_tickets.select("ticket_id").distinct().count()
duplicate_remaining = total_tickets - distinct_ticket_ids
add_check(3, "チケットID重複解消", 0, duplicate_remaining,
          "全件数と一意ticket_id数の差分（0であれば重複なし）")

# ──────────────────────────────────────────────
# 4. created_atがTIMESTAMP型に標準化されているか（Bronzeでは生データのためSTRING型）
# ──────────────────────────────────────────────
created_at_type = dict(df_support_tickets.dtypes).get("created_at")
add_check(4, "created_atのTIMESTAMP型化", "timestamp", created_at_type,
          "Gold層で日次集計するためTIMESTAMP型になっている必要がある")

# ──────────────────────────────────────────────
# 5. created_atのパースに失敗しNULLになった行がないか
# ──────────────────────────────────────────────
created_at_null_count = df_support_tickets.filter(F.col("created_at").isNull()).count()
add_check(5, "created_atパース漏れなし", 0, created_at_null_count,
          "複数フォーマット対応後もパースできなかった件数")

# ──────────────────────────────────────────────
# 6. 解決時間の異常値（720時間超）が残っていないか
# ──────────────────────────────────────────────
resolution_outlier_remaining = df_support_tickets.filter(
    F.col("resolution_hours") > RESOLUTION_HOURS_MAX
).count()
add_check(6, "解決時間の異常値解消", 0, resolution_outlier_remaining,
          "resolution_hoursが720時間を超える残存件数（NULLに無効化されているはず）")

# ──────────────────────────────────────────────
# 7. 顧客ID不一致・欠損が削除されず、正しくフラグ管理されているか
#    （直せない欠損のため削除せず is_customer_id_valid / data_quality_flags で可視化する設計）
# ──────────────────────────────────────────────
invalid_customer_unflagged = df_support_tickets.filter(
    (~F.col("is_customer_id_valid"))
    & (~F.array_contains(F.col("data_quality_flags"), "customer_id_null"))
    & (~F.array_contains(F.col("data_quality_flags"), "customer_id_unmatched"))
).count()
add_check(7, "顧客ID不一致・欠損のフラグ管理", 0, invalid_customer_unflagged,
          "is_customer_id_valid=falseなのにdata_quality_flagsに記録されていない件数")

# ──────────────────────────────────────────────
# 8. カテゴリ・センチメント欠損がねつ造されずNULLのまま、かつフラグ記録されているか
# ──────────────────────────────────────────────
category_null_unflagged = df_support_tickets.filter(
    F.col("category").isNull() & (~F.array_contains(F.col("data_quality_flags"), "category_null"))
).count()
sentiment_null_unflagged = df_support_tickets.filter(
    F.col("sentiment").isNull() & (~F.array_contains(F.col("data_quality_flags"), "sentiment_null"))
).count()
add_check(8, "カテゴリ/センチメント欠損のフラグ管理", 0,
          category_null_unflagged + sentiment_null_unflagged,
          "NULLなのにdata_quality_flagsに記録されていない件数の合計")

# ──────────────────────────────────────────────
# 9. 品質課題フラグの総数が、意図した件数と一致するか
#    （generate_and_save_sample_data.py で埋め込んだ27件。重複2件はticket_id
#      重複排除で1レコードに統合されるため、Silverの全51件中27件が対象）
# ──────────────────────────────────────────────
flagged_ticket_count = df_support_tickets.filter(F.size("data_quality_flags") > 0).count()
add_check(9, "品質課題フラグの整合性", 27, flagged_ticket_count,
          "data_quality_flagsが1件以上あるチケット数（意図した27件と一致するか）")


df_check_results = spark.createDataFrame(
    checks, ["check_no", "check_name", "expected", "actual", "result", "description"]
)
print("=== Silverレイヤー 品質チェック結果 ===")
display(df_check_results)

all_pass = all(c[4] == "PASS" for c in checks)
print(f"\n総合判定: {'すべてPASS（意図した品質改善が実現できている）' if all_pass else 'FAILあり（要確認）'}")


# ──────────────────────────────────────────────
# 10. Gold層で計画している4集計が実際に算出可能かの確認
#     （Knowledge baseのGold出力要件を満たせるかをSilverデータで検証）
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== Gold層集計の実行可否確認（Silverデータで試算） ===")
print("=" * 60)

# (a) サポートに関する日次KPI
print("\n--- (a) 日次KPI: 日次チケット数・高優先度数・未解決数・平均解決時間 ---")
daily_kpi = (
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
display(daily_kpi)

# (b) カスタマーサポートのリスク分析（顧客単位）
print("\n--- (b) 顧客単位のリスク分析: 件数・高優先度・ネガティブ・未解決・平均解決時間 ---")
customer_risk = (
    df_support_tickets
    .filter(F.col("is_customer_id_valid"))  # customer_masterに存在しない/NULLは除外
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("ticket_count"),
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.sum(F.when(F.col("sentiment") == "Negative", 1).otherwise(0)).alias("negative_count"),
        F.sum(F.when(F.col("status").isin(UNRESOLVED_STATUSES), 1).otherwise(0)).alias("unresolved_count"),
        F.round(F.avg("resolution_hours"), 1).alias("avg_resolution_hours"),
    )
    .join(df_customer_master.select("customer_id", "company_name", "csm_owner"), "customer_id", "left")
    .orderBy(F.desc("high_priority_count"), F.desc("negative_count"))
)
display(customer_risk)

# (c) カテゴリごとのサポート集計
print("\n--- (c) カテゴリ別・日別のチケット数・高優先度数・平均解決時間 ---")
category_summary = (
    df_support_tickets
    .withColumn("ticket_date", F.to_date("created_at"))
    .groupBy("category", "ticket_date")
    .agg(
        F.count("*").alias("ticket_count"),
        F.sum(F.when(F.col("priority") == "High", 1).otherwise(0)).alias("high_priority_count"),
        F.round(F.avg("resolution_hours"), 1).alias("avg_resolution_hours"),
    )
    .orderBy("ticket_date", "category")
)
display(category_summary)

# (d) データ品質サマリ（品質課題種別ごとの件数）
print("\n--- (d) データ品質サマリ: 品質課題の種類別件数 ---")
quality_summary = (
    df_support_tickets
    .withColumn("issue", F.explode_outer("data_quality_flags"))
    .filter(F.col("issue").isNotNull())
    .groupBy("issue")
    .count()
    .orderBy(F.desc("count"))
)
display(quality_summary)

print("\n=== Gold層集計がSilverデータで問題なく算出できることを確認しました ===")
