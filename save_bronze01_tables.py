# Databricks ノートブック用
# サンプルデータ（df_users / df_subscriptions / df_events）を
# 一切変更せずに Bronze レイヤーの Delta テーブルとして保存する
#
# 前提：generate_cloudbox_sample_data.py を同セッションで実行済みであること
#       （df_users, df_subscriptions, df_events が生成済みであること）
# 動作確認環境：Databricks Free Edition
#
# 保存先スキーマ: bronze01（存在しない場合は作成する）
#
# 方針：
#   - ビジネスカラムの値は一切変更・加工しない（品質課題を含むデータもそのまま保存する）
#   - 取り込み履歴を追跡するための取り込みメタデータ列のみを追加する
#     （_bronze_ingested_at: 取り込み日時 / _bronze_source: 取り込み元識別子）
#
# 【重要】表を先にSQL DDLで作成してからデータを書き込む理由:
#   df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(...)
#   のように「DataFrameのスキーマから表を作らせる」書き方をすると、
#   df側で nullable=False（NOT NULL）に定義していた列（例: user_id, subscription_id, event_id）が
#   Delta保存時に nullable=True へ緩和されてしまい、verify_bronze01_raw_integrity.py の
#   スキーマ一致チェックが意図せずFALSEになる。
#   これを避けるため、CREATE TABLE ... USING DELTA のSQL DDLで
#   NOT NULL制約を明示した空テーブルを先に作成し、
#   その後 overwriteSchema オプションを使わずにデータだけを書き込む
#   （既存テーブルのスキーマ定義がそのまま保持されることをローカル検証で確認済み）。

from pyspark.sql import functions as F

BRONZE_SCHEMA = "bronze01"
SOURCE_SYSTEM_NAME = "cloudbox_sample_data_generator"


# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
# ──────────────────────────────────────────────

spark.sql(f"CREATE DATABASE IF NOT EXISTS {BRONZE_SCHEMA}")
spark.sql(f"USE {BRONZE_SCHEMA}")

print(f"データベース '{BRONZE_SCHEMA}' を選択しました")


def add_ingestion_metadata(df):
    """ビジネスカラムには一切手を加えず、取り込みメタデータ列のみを付与する"""
    return (
        df
        .withColumn("_bronze_ingested_at", F.current_timestamp())  # 取り込み日時
        .withColumn("_bronze_source", F.lit(SOURCE_SYSTEM_NAME))   # 取り込み元識別子
    )


# ──────────────────────────────────────────────
# 1. ユーザーマスター → bronze01.bronze_users
#    （user_id は生成元スキーマと同じく NOT NULL として表を定義する）
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {BRONZE_SCHEMA}.bronze_users (
  user_id             STRING    NOT NULL,
  user_name           STRING,
  email               STRING,
  country_code        STRING,
  signup_platform     STRING,
  signup_date         DATE,
  _bronze_ingested_at TIMESTAMP,
  _bronze_source      STRING
)
USING DELTA
""")

# CREATE TABLE の列順序に合わせて明示的に並べ替えてから書き込む
df_users_bronze = add_ingestion_metadata(df_users).select(
    "user_id", "user_name", "email", "country_code", "signup_platform", "signup_date",
    "_bronze_ingested_at", "_bronze_source",
)

(
    df_users_bronze
    .write
    .format("delta")
    .mode("overwrite")  # overwriteSchemaは指定しない（既存テーブルのNOT NULL定義を保持するため）
    .saveAsTable(f"{BRONZE_SCHEMA}.bronze_users")
)

users_count = spark.table(f"{BRONZE_SCHEMA}.bronze_users").count()
print(f"bronze_users 保存完了: {users_count:,} 件")


# ──────────────────────────────────────────────
# 2. サブスクリプションデータ → bronze01.bronze_subscriptions
#    （subscription_id は生成元スキーマと同じく NOT NULL として表を定義する）
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {BRONZE_SCHEMA}.bronze_subscriptions (
  subscription_id      STRING    NOT NULL,
  user_id              STRING,
  plan_type            STRING,
  payment_status       STRING,
  amount               DOUBLE,
  payment_date         STRING,
  contract_start_date  DATE,
  contract_end_date    DATE,
  _bronze_ingested_at  TIMESTAMP,
  _bronze_source       STRING
)
USING DELTA
""")

df_subscriptions_bronze = add_ingestion_metadata(df_subscriptions).select(
    "subscription_id", "user_id", "plan_type", "payment_status", "amount",
    "payment_date", "contract_start_date", "contract_end_date",
    "_bronze_ingested_at", "_bronze_source",
)

(
    df_subscriptions_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{BRONZE_SCHEMA}.bronze_subscriptions")
)

subscriptions_count = spark.table(f"{BRONZE_SCHEMA}.bronze_subscriptions").count()
print(f"bronze_subscriptions 保存完了: {subscriptions_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーアクションイベントログ → bronze01.bronze_user_events
#    （event_id は生成元スキーマと同じく NOT NULL として表を定義する）
# ──────────────────────────────────────────────

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {BRONZE_SCHEMA}.bronze_user_events (
  event_id             STRING    NOT NULL,
  user_id              STRING,
  event_type           STRING,
  event_timestamp      TIMESTAMP,
  ingestion_timestamp  TIMESTAMP,
  _bronze_ingested_at  TIMESTAMP,
  _bronze_source       STRING
)
USING DELTA
""")

df_events_bronze = add_ingestion_metadata(df_events).select(
    "event_id", "user_id", "event_type", "event_timestamp", "ingestion_timestamp",
    "_bronze_ingested_at", "_bronze_source",
)

(
    df_events_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{BRONZE_SCHEMA}.bronze_user_events")
)

events_count = spark.table(f"{BRONZE_SCHEMA}.bronze_user_events").count()
print(f"bronze_user_events 保存完了: {events_count:,} 件")


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print(f"=== {BRONZE_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_users         : {users_count:>6,} 件")
print(f"  bronze_subscriptions : {subscriptions_count:>6,} 件")
print(f"  bronze_user_events   : {events_count:>6,} 件")
print("=" * 40)
