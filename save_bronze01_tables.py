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
# ──────────────────────────────────────────────

df_users_bronze = add_ingestion_metadata(df_users)

(
    df_users_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{BRONZE_SCHEMA}.bronze_users")
)

users_count = spark.table(f"{BRONZE_SCHEMA}.bronze_users").count()
print(f"bronze_users 保存完了: {users_count:,} 件")


# ──────────────────────────────────────────────
# 2. サブスクリプションデータ → bronze01.bronze_subscriptions
# ──────────────────────────────────────────────

df_subscriptions_bronze = add_ingestion_metadata(df_subscriptions)

(
    df_subscriptions_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{BRONZE_SCHEMA}.bronze_subscriptions")
)

subscriptions_count = spark.table(f"{BRONZE_SCHEMA}.bronze_subscriptions").count()
print(f"bronze_subscriptions 保存完了: {subscriptions_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーアクションイベントログ → bronze01.bronze_user_events
# ──────────────────────────────────────────────

df_events_bronze = add_ingestion_metadata(df_events)

(
    df_events_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
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
