# Databricks ノートブック用
# Cloudbox Bronze層サンプルデータの検証レポート
#
# 表示内容：
#   1. 各表のサンプルデータ（先頭数件）
#   2. 各表の件数
#   3. 品質課題データの件数
#   4. 意図的に含めた品質課題一覧
#
# 前提：generate_cloudbox_sample_data.py と save_cloudbox_bronze_delta_tables.py を
#       同セッションで実行済みであること（cloudbox_bronze.* テーブルが存在すること）

from pyspark.sql import Row
from pyspark.sql import functions as F

print("=" * 60)
print("Cloudbox Bronze層 サンプルデータ検証レポート")
print("=" * 60)


# ──────────────────────────────────────────────
# 1. bronze_users
# ──────────────────────────────────────────────

df_u = spark.table("cloudbox_bronze.bronze_users")

print("\n--- bronze_users ---")
print(f"総件数: {df_u.count()} 件")
df_u.show(10, truncate=False)

JP_VARIANTS = ["jp", "jpn", "Japan", "JAPAN"]
bad_country_df = df_u.filter(F.col("country_code").isin(JP_VARIANTS))
bad_country_count = bad_country_df.count()

print(f"[品質課題] country_code表記揺れ件数: {bad_country_count} 件")
bad_country_df.show(truncate=False)

valid_user_ids = [r.user_id for r in df_u.select("user_id").collect()]


# ──────────────────────────────────────────────
# 2. bronze_subscriptions
# ──────────────────────────────────────────────

df_s = spark.table("cloudbox_bronze.bronze_subscriptions")

print("\n--- bronze_subscriptions ---")
print(f"総件数: {df_s.count()} 件")
df_s.show(10, truncate=False)

null_userid_sub_df = df_s.filter(F.col("user_id").isNull())
null_userid_sub = null_userid_sub_df.count()

orphan_userid_sub_df = df_s.filter(
    F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids))
)
orphan_userid_sub = orphan_userid_sub_df.count()

# 標準フォーマット(YYYY-MM-DD)以外を不正フォーマットとみなす
bad_date_sub_df = df_s.filter(~F.col("payment_date").rlike(r"^\d{4}-\d{2}-\d{2}$"))
bad_date_sub = bad_date_sub_df.count()

bad_amount_sub_df = df_s.filter(F.col("amount") <= 0)
bad_amount_sub = bad_amount_sub_df.count()

VALID_PAYMENT_STATUSES = ["success", "failed", "pending", "refunded"]
bad_status_sub_df = df_s.filter(~F.col("payment_status").isin(VALID_PAYMENT_STATUSES))
bad_status_sub = bad_status_sub_df.count()

print(f"[品質課題] user_idがnull: {null_userid_sub} 件")
print(f"[品質課題] user masterに存在しないuser_id: {orphan_userid_sub} 件")
print(f"[品質課題] payment_dateのフォーマット不整合: {bad_date_sub} 件")
bad_date_sub_df.select("subscription_id", "payment_date").show(truncate=False)
print(f"[品質課題] amountが0または負値: {bad_amount_sub} 件")
bad_amount_sub_df.select("subscription_id", "amount").show(truncate=False)
print(f"[品質課題] payment_statusが想定外の値: {bad_status_sub} 件")
bad_status_sub_df.select("subscription_id", "payment_status").show(truncate=False)


# ──────────────────────────────────────────────
# 3. bronze_user_events
# ──────────────────────────────────────────────

df_e = spark.table("cloudbox_bronze.bronze_user_events")

print("\n--- bronze_user_events ---")
print(f"総件数: {df_e.count()} 件")
df_e.show(10, truncate=False)

null_userid_evt = df_e.filter(F.col("user_id").isNull()).count()

orphan_userid_evt_df = df_e.filter(
    F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids))
)
orphan_userid_evt = orphan_userid_evt_df.count()

dup_event_id_df = df_e.groupBy("event_id").count().filter(F.col("count") > 1)
dup_event_rows = dup_event_id_df.agg(F.sum("count")).collect()[0][0] or 0

# event_timestampとingestion_timestampの乖離が1日(86400秒)以上のものを遅延到着とみなす
delayed_evt_df = df_e.filter(
    (F.col("ingestion_timestamp").cast("long") - F.col("event_timestamp").cast("long")) >= 86400
)
delayed_evt = delayed_evt_df.count()

print(f"[品質課題] user_idがnull: {null_userid_evt} 件")
print(f"[品質課題] user masterに存在しないuser_id: {orphan_userid_evt} 件")
print(f"[品質課題] event_idの重複到着（重複行数合計）: {dup_event_rows} 件")
dup_event_id_df.show(truncate=False)
print(f"[品質課題] イベントの遅延到着（1日以上の乖離）: {delayed_evt} 件")
delayed_evt_df.select("event_id", "event_timestamp", "ingestion_timestamp").show(truncate=False)


# ──────────────────────────────────────────────
# 4. 意図的に含めた品質課題一覧
# ──────────────────────────────────────────────

quality_summary_rows = [
    Row(table_name="bronze_users",         quality_issue="country_codeの表記揺れ(jp/jpn/Japan/JAPAN)", issue_count=bad_country_count),
    Row(table_name="bronze_subscriptions", quality_issue="user_idがnull",                              issue_count=null_userid_sub),
    Row(table_name="bronze_subscriptions", quality_issue="user masterに存在しないuser_id",               issue_count=orphan_userid_sub),
    Row(table_name="bronze_subscriptions", quality_issue="payment_dateのフォーマット不整合",              issue_count=bad_date_sub),
    Row(table_name="bronze_subscriptions", quality_issue="amountが0または負値",                          issue_count=bad_amount_sub),
    Row(table_name="bronze_subscriptions", quality_issue="payment_statusが想定外の値",                    issue_count=bad_status_sub),
    Row(table_name="bronze_user_events",   quality_issue="user_idがnull",                              issue_count=null_userid_evt),
    Row(table_name="bronze_user_events",   quality_issue="user masterに存在しないuser_id",               issue_count=orphan_userid_evt),
    Row(table_name="bronze_user_events",   quality_issue="event_idの重複到着",                          issue_count=int(dup_event_rows)),
    Row(table_name="bronze_user_events",   quality_issue="イベントの遅延到着(1日以上の乖離)",             issue_count=delayed_evt),
]
df_quality_summary = spark.createDataFrame(quality_summary_rows)

print("\n" + "=" * 60)
print("=== 意図的に含めた品質課題一覧 ===")
print("=" * 60)
df_quality_summary.show(truncate=False)

total_issue_rows = sum(r.issue_count for r in quality_summary_rows)
print(f"品質課題の合計件数（延べ）: {total_issue_rows} 件")
