# Databricks ノートブック用
# bronze01層のデータを品質改善し、silverスキーマの表として保存する
#
# 前提：bronze01.bronze_users / bronze_subscriptions / bronze_user_events が
#       保存済みであること（save_bronze01_tables.py 実行済み）
# 動作確認環境：Databricks Free Edition
#
# 方針：
#   - Knowledge baseに列挙された品質課題のうち、根拠を持って自動修正できるもの
#     （country_codeの表記揺れ／payment_dateのフォーマット揺れ／event_idの重複）は
#     実際に値を補正・重複排除する。
#   - 根拠なく値を捏造できないもの（user_idのnull/マスター不一致、amountの0/負値、
#     payment_statusの想定外の値）は値を書き換えず、"is_valid_for_gold" フラグで
#     Gold集計から除外すべきレコードであることを明示する。
#   - どの品質課題を検知・補正したかを dq_issues 列にカンマ区切りで記録し、
#     データチームが状況を追跡できるようにする。
#   - 表は先にSQL DDL（NOT NULL制約つき）で作成してから、
#     overwriteSchemaオプションを使わずにデータを書き込む
#     （saveAsTable + overwriteSchema=true はNOT NULL制約を失わせるため。
#       bronze01層の修正時に確認済みの注意点）。

from pyspark.sql import functions as F
from pyspark.sql.window import Window

SILVER_SCHEMA = "silver"
BRONZE_SCHEMA = "bronze01"

VALID_PAYMENT_STATUSES = ["success", "failed", "pending", "refunded"]
JP_COUNTRY_VARIANTS = ["jp", "jpn", "Japan", "JAPAN"]  # 本来 "JP" に統一されるべき表記揺れ

spark.sql(f"CREATE DATABASE IF NOT EXISTS {SILVER_SCHEMA}")
spark.sql(f"USE {SILVER_SCHEMA}")

print(f"データベース '{SILVER_SCHEMA}' を選択しました")


# ──────────────────────────────────────────────
# 1. silver_users
#    品質改善: country_code の表記揺れを "JP" 等の正規コードへ補正
#    is_valid_for_gold: user masterには回復不能な課題が無いため常にTrue
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {SILVER_SCHEMA}.silver_users (
  user_id              STRING    NOT NULL,
  user_name            STRING,
  email                STRING,
  country_code         STRING,
  signup_platform       STRING,
  signup_date           DATE,
  dq_issues             STRING,
  is_valid_for_gold     BOOLEAN NOT NULL,
  _silver_processed_at  TIMESTAMP
)
USING DELTA
""")

df_bronze_users = spark.table(f"{BRONZE_SCHEMA}.bronze_users")

df_silver_users = (
    df_bronze_users
    .withColumn(
        "country_code_cleansed",
        F.when(F.col("country_code").isin(JP_COUNTRY_VARIANTS), F.lit("JP"))
         .otherwise(F.upper(F.col("country_code")))
    )
    .withColumn(
        "dq_issues",
        F.when(F.col("country_code").isin(JP_COUNTRY_VARIANTS), F.lit("country_code_variant_corrected"))
    )
    .withColumn("is_valid_for_gold", F.lit(True))  # user masterに回復不能な課題は無い
    .withColumn("_silver_processed_at", F.current_timestamp())
    .drop("country_code")
    .withColumnRenamed("country_code_cleansed", "country_code")
    .select(
        "user_id", "user_name", "email", "country_code", "signup_platform", "signup_date",
        "dq_issues", "is_valid_for_gold", "_silver_processed_at",
    )
)

(
    df_silver_users
    .write
    .format("delta")
    .mode("overwrite")  # overwriteSchemaは指定しない（既存テーブルのNOT NULL定義を保持するため）
    .saveAsTable(f"{SILVER_SCHEMA}.silver_users")
)

users_count = spark.table(f"{SILVER_SCHEMA}.silver_users").count()
print(f"silver_users 保存完了: {users_count:,} 件")

# 後続表のFK検証で使用（user masterに実在するuser_id一覧）
valid_user_ids = [r.user_id for r in spark.table(f"{SILVER_SCHEMA}.silver_users").select("user_id").collect()]


# ──────────────────────────────────────────────
# 2. silver_subscriptions
#    品質改善:
#      - payment_date のフォーマット揺れを解析してDATE型に補正（生値は payment_date_raw に保持）
#      - payment_status を正規値(success/failed/pending/refunded)に正規化。
#        正規値に当てはまらない場合は "unknown" とし、Gold集計対象外とする
#    是正不能なため is_valid_for_gold=False とする課題:
#      - user_idがnull／user masterに存在しないuser_id
#      - amountが0以下
#      - payment_statusが正規値に正規化できない
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {SILVER_SCHEMA}.silver_subscriptions (
  subscription_id       STRING    NOT NULL,
  user_id               STRING,
  plan_type              STRING,
  payment_status_raw      STRING,
  payment_status           STRING,
  amount                    DOUBLE,
  payment_date_raw           STRING,
  payment_date                DATE,
  contract_start_date          DATE,
  contract_end_date             DATE,
  dq_issues                      STRING,
  is_valid_for_gold                BOOLEAN NOT NULL,
  _silver_processed_at               TIMESTAMP
)
USING DELTA
""")

df_bronze_subs = spark.table(f"{BRONZE_SCHEMA}.bronze_subscriptions")

df_silver_subscriptions = (
    df_bronze_subs
    .withColumnRenamed("payment_date", "payment_date_raw")
    .withColumnRenamed("payment_status", "payment_status_raw")
    # payment_date: 想定される複数フォーマットを順に試し、最初に成功した解析結果を採用する
    .withColumn(
        "payment_date",
        F.coalesce(
            F.to_date("payment_date_raw", "yyyy-MM-dd"),    # 標準フォーマット
            F.to_date("payment_date_raw", "yyyy/MM/dd"),
            F.to_date("payment_date_raw", "dd-MM-yyyy"),
            F.to_date("payment_date_raw", "MM/dd/yyyy"),
            F.to_date("payment_date_raw", "MMMM d, yyyy"),
        )
    )
    # payment_status: 前後空白・大小文字を正規化し、正規値以外は "unknown" に丸める
    .withColumn(
        "payment_status",
        F.when(
            F.trim(F.lower(F.col("payment_status_raw"))).isin(VALID_PAYMENT_STATUSES),
            F.trim(F.lower(F.col("payment_status_raw"))),
        ).otherwise(F.lit("unknown"))
    )
    .withColumn("_is_user_id_missing", F.col("user_id").isNull())
    .withColumn("_is_user_id_orphan", F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids)))
    .withColumn("_is_amount_invalid", F.col("amount") <= 0)
    .withColumn(
        "_is_payment_status_invalid",
        ~F.trim(F.lower(F.col("payment_status_raw"))).isin(VALID_PAYMENT_STATUSES)
    )
    .withColumn("_is_payment_date_unparseable", F.col("payment_date").isNull())
    .withColumn(
        "dq_issues",
        F.nullif(  # concat_wsは該当課題が無い場合に空文字列を返すため、NULLに統一する
            F.concat_ws(
                ",",
                F.when(F.col("_is_user_id_missing"), F.lit("user_id_null")),
                F.when(F.col("_is_user_id_orphan"), F.lit("user_id_orphan")),
                F.when(F.col("_is_amount_invalid"), F.lit("invalid_amount")),
                F.when(F.col("_is_payment_status_invalid"), F.lit("invalid_payment_status")),
                F.when(F.col("_is_payment_date_unparseable"), F.lit("payment_date_unparseable"))
                 .when(F.col("payment_date_raw") != F.date_format(F.col("payment_date"), "yyyy-MM-dd"),
                       F.lit("payment_date_format_corrected")),
            ),
            F.lit(""),
        )
    )
    .withColumn(
        "is_valid_for_gold",
        ~(
            F.col("_is_user_id_missing")
            | F.col("_is_user_id_orphan")
            | F.col("_is_amount_invalid")
            | F.col("_is_payment_status_invalid")
            | F.col("_is_payment_date_unparseable")
        )
    )
    .withColumn("_silver_processed_at", F.current_timestamp())
    .select(
        "subscription_id", "user_id", "plan_type",
        "payment_status_raw", "payment_status",
        "amount",
        "payment_date_raw", "payment_date",
        "contract_start_date", "contract_end_date",
        "dq_issues", "is_valid_for_gold", "_silver_processed_at",
    )
)

(
    df_silver_subscriptions
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{SILVER_SCHEMA}.silver_subscriptions")
)

subscriptions_count = spark.table(f"{SILVER_SCHEMA}.silver_subscriptions").count()
print(f"silver_subscriptions 保存完了: {subscriptions_count:,} 件")


# ──────────────────────────────────────────────
# 3. silver_user_events
#    品質改善: event_idの重複到着を排除する（同一event_idは最も早いevent_timestampの1件のみ残す）
#    是正不能なため is_valid_for_gold=False とする課題:
#      - user_idがnull／user masterに存在しないuser_id
#    参考情報として残すが無効化はしない課題:
#      - イベントの遅延到着（is_delayed_arrival列で可視化。データ自体は有効なため除外しない）
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {SILVER_SCHEMA}.silver_user_events (
  event_id              STRING    NOT NULL,
  user_id               STRING,
  event_type             STRING,
  event_timestamp         TIMESTAMP,
  ingestion_timestamp      TIMESTAMP,
  is_delayed_arrival        BOOLEAN NOT NULL,
  dq_issues                  STRING,
  is_valid_for_gold            BOOLEAN NOT NULL,
  _silver_processed_at           TIMESTAMP
)
USING DELTA
""")

df_bronze_events = spark.table(f"{BRONZE_SCHEMA}.bronze_user_events")

# 重複するevent_idは、event_timestampが最も早い1件のみを残す
dedup_window = Window.partitionBy("event_id").orderBy(F.col("event_timestamp").asc_nulls_last())
df_events_ranked = df_bronze_events.withColumn("_dup_rank", F.row_number().over(dedup_window))

duplicate_removed_count = df_events_ranked.filter(F.col("_dup_rank") > 1).count()
df_events_deduped = df_events_ranked.filter(F.col("_dup_rank") == 1).drop("_dup_rank")

df_silver_user_events = (
    df_events_deduped
    .withColumn("_is_user_id_missing", F.col("user_id").isNull())
    .withColumn("_is_user_id_orphan", F.col("user_id").isNotNull() & (~F.col("user_id").isin(valid_user_ids)))
    .withColumn(
        "is_delayed_arrival",
        (F.col("ingestion_timestamp").cast("long") - F.col("event_timestamp").cast("long")) >= 86400
    )
    .withColumn(
        "dq_issues",
        F.nullif(  # concat_wsは該当課題が無い場合に空文字列を返すため、NULLに統一する
            F.concat_ws(
                ",",
                F.when(F.col("_is_user_id_missing"), F.lit("user_id_null")),
                F.when(F.col("_is_user_id_orphan"), F.lit("user_id_orphan")),
                F.when(F.col("is_delayed_arrival"), F.lit("delayed_arrival")),
            ),
            F.lit(""),
        )
    )
    .withColumn(
        "is_valid_for_gold",
        ~(F.col("_is_user_id_missing") | F.col("_is_user_id_orphan"))
    )
    .withColumn("_silver_processed_at", F.current_timestamp())
    .select(
        "event_id", "user_id", "event_type", "event_timestamp", "ingestion_timestamp",
        "is_delayed_arrival", "dq_issues", "is_valid_for_gold", "_silver_processed_at",
    )
)

(
    df_silver_user_events
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{SILVER_SCHEMA}.silver_user_events")
)

events_count = spark.table(f"{SILVER_SCHEMA}.silver_user_events").count()
print(f"silver_user_events 保存完了: {events_count:,} 件（重複排除: {duplicate_removed_count} 件）")


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print(f"=== {SILVER_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
print(f"  silver_users          : {users_count:>6,} 件")
print(f"  silver_subscriptions  : {subscriptions_count:>6,} 件")
print(f"  silver_user_events    : {events_count:>6,} 件（重複排除 {duplicate_removed_count} 件）")
print("=" * 40)
