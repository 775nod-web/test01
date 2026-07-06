# Databricks ノートブック用
# 生成済み DataFrame（df_users / df_subscriptions / df_events）を
# Bronze レイヤーの Delta テーブルとして保存する
#
# 前提：generate_cloudbox_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition
#
# ecommerce サンプル（bronze.bronze_users 等）と表名が衝突しないよう、
# Cloudbox 用は専用データベース "cloudbox_bronze" に保存する

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS cloudbox_bronze")
spark.sql("USE cloudbox_bronze")

print("データベース 'cloudbox_bronze' を選択しました")


# ──────────────────────────────────────────────
# 1. ユーザーマスター → bronze_users
# ──────────────────────────────────────────────

(
    df_users
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("cloudbox_bronze.bronze_users")
)

users_count = spark.table("cloudbox_bronze.bronze_users").count()
print(f"bronze_users 保存完了: {users_count:,} 件")


# ──────────────────────────────────────────────
# 2. サブスクリプションデータ → bronze_subscriptions
# ──────────────────────────────────────────────

(
    df_subscriptions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("cloudbox_bronze.bronze_subscriptions")
)

subscriptions_count = spark.table("cloudbox_bronze.bronze_subscriptions").count()
print(f"bronze_subscriptions 保存完了: {subscriptions_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーアクションイベントログ → bronze_user_events
# ──────────────────────────────────────────────

(
    df_events
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("cloudbox_bronze.bronze_user_events")
)

events_count = spark.table("cloudbox_bronze.bronze_user_events").count()
print(f"bronze_user_events 保存完了: {events_count:,} 件")


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Cloudbox Bronze レイヤー 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_users         : {users_count:>6,} 件")
print(f"  bronze_subscriptions : {subscriptions_count:>6,} 件")
print(f"  bronze_user_events   : {events_count:>6,} 件")
print("=" * 40)


# ──────────────────────────────────────────────
# 5. Delta テーブルの履歴確認（任意）
# ──────────────────────────────────────────────

print("\n=== bronze_users の Delta 履歴 ===")
spark.sql("DESCRIBE HISTORY cloudbox_bronze.bronze_users").select(
    "version", "timestamp", "operation", "operationParameters"
).show(truncate=False)
