# Databricks ノートブック用
# 生成済み DataFrame（df_gameplay_log / df_purchase / df_user_master）を
# Bronze レイヤーの Delta テーブルとして保存する
#
# 前提：generate_game_sample_data.py を同セッションで実行済みであること
# 保存先：スキーマ = interview_prep、ボリューム = interview_prep_volume
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

# ──────────────────────────────────────────────
# 0. スキーマ（データベース）とボリュームの作成
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS interview_prep")
spark.sql("USE interview_prep")

# ボリューム（外部ファイル格納用パス）は手動作成または管理者が事前作成する想定。
# Hive メタストア環境では VOLUME DDL は不要のため、Delta テーブルとして直接保存する。

print("スキーマ 'interview_prep' を選択しました")


# ──────────────────────────────────────────────
# 1. ゲームプレイログ → bronze_gameplay_log
#    ストリーミング取り込み想定のため event_ts で日付パーティションを付与
# ──────────────────────────────────────────────

from pyspark.sql.functions import to_date, col

(
    df_gameplay_log
    .withColumn("event_date", to_date(col("event_ts")))   # パーティションキー
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("event_date")                             # 日次バッチ処理・フィルタ最適化
    .saveAsTable("interview_prep.bronze_gameplay_log")
)

gameplay_count = spark.table("interview_prep.bronze_gameplay_log").count()
print(f"bronze_gameplay_log 保存完了: {gameplay_count:,} 件")


# ──────────────────────────────────────────────
# 2. 課金データ → bronze_purchase
# ──────────────────────────────────────────────

(
    df_purchase
    .withColumn("purchase_date", to_date(col("purchase_ts")))
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("purchase_date")
    .saveAsTable("interview_prep.bronze_purchase")
)

purchase_count = spark.table("interview_prep.bronze_purchase").count()
print(f"bronze_purchase 保存完了: {purchase_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーマスター → bronze_user_master
#    日次バッチ想定のためパーティションなし（全件上書き）
# ──────────────────────────────────────────────

(
    df_user_master
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("interview_prep.bronze_user_master")
)

user_count = spark.table("interview_prep.bronze_user_master").count()
print(f"bronze_user_master 保存完了: {user_count:,} 件")


# ──────────────────────────────────────────────
# 4. 保存結果サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== Bronze レイヤー 保存完了サマリー ===")
print("=" * 50)
print(f"  bronze_gameplay_log : {gameplay_count:>6,} 件  （パーティション: event_date）")
print(f"  bronze_purchase     : {purchase_count:>6,} 件  （パーティション: purchase_date）")
print(f"  bronze_user_master  : {user_count:>6,} 件  （パーティションなし）")
print("=" * 50)


# ──────────────────────────────────────────────
# 5. Delta 履歴の確認（任意）
# ──────────────────────────────────────────────

print("\n=== bronze_gameplay_log の Delta 履歴 ===")
spark.sql("DESCRIBE HISTORY interview_prep.bronze_gameplay_log").select(
    "version", "timestamp", "operation", "operationParameters"
).show(3, truncate=False)


# ──────────────────────────────────────────────
# 6. 保存データの先頭5件確認
# ──────────────────────────────────────────────

print("\n=== bronze_gameplay_log 先頭5件 ===")
spark.table("interview_prep.bronze_gameplay_log").show(5, truncate=False)

print("\n=== bronze_purchase 先頭5件 ===")
spark.table("interview_prep.bronze_purchase").show(5, truncate=False)

print("\n=== bronze_user_master 先頭5件 ===")
spark.table("interview_prep.bronze_user_master").show(5, truncate=False)


# ──────────────────────────────────────────────
# 7. データ品質確認（Bronze はあえてチェックのみ、修正はしない）
# ──────────────────────────────────────────────

print("\n=== データ品質チェック（Bronze 生データ確認） ===")

null_event = spark.table("interview_prep.bronze_gameplay_log") \
    .filter("event_type IS NULL").count()
print(f"  [1] event_type が Null のレコード数 : {null_event} 件  → Silver 層で対処予定")

unmatched_users = spark.table("interview_prep.bronze_gameplay_log") \
    .join(
        spark.table("interview_prep.bronze_user_master"),
        on="user_id",
        how="left_anti"   # マスター未登録の user_id を抽出
    ).select("user_id").distinct().count()
print(f"  [2] マスター未登録ユーザー種別数   : {unmatched_users} 件  → Silver 層で名寄せ予定")
