# Databricks ノートブック用
# 生成済み DataFrame を Bronze レイヤーの Delta テーブルとして保存する
#
# 前提：generate_game_sample_data.py を同セッションで実行済みであること
# 保存先スキーマ：interview_prep
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

%python
from pyspark.sql import functions as F

# ──────────────────────────────────────────────
# 0. スキーマ（データベース）の作成・切り替え
# ──────────────────────────────────────────────

# スキーマが存在しない場合のみ作成（冪等性を確保）
spark.sql("CREATE DATABASE IF NOT EXISTS interview_prep")
spark.sql("USE interview_prep")

print("スキーマ 'interview_prep' を選択しました")


# ──────────────────────────────────────────────
# 1. ゲームプレイログ → bronze_gameplay_log
# ──────────────────────────────────────────────

(
    df_gameplay_log
    # event_ts から日付カラムを生成してパーティションキーに使用
    .withColumn("event_date", F.to_date(F.col("event_ts")))
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .partitionBy("event_date")            # 日付でパーティション分割（クエリ高速化）
    .saveAsTable("interview_prep.bronze_gameplay_log")
)

# 保存件数を確認
gameplay_count = spark.table("interview_prep.bronze_gameplay_log").count()
print(f"bronze_gameplay_log 保存完了: {gameplay_count:,} 件")


# ──────────────────────────────────────────────
# 2. 課金データ → bronze_purchase
# ──────────────────────────────────────────────

(
    df_purchase
    # purchase_ts から日付カラムを生成してパーティションキーに使用
    .withColumn("purchase_date", F.to_date(F.col("purchase_ts")))
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .partitionBy("purchase_date")         # 日付でパーティション分割（クエリ高速化）
    .saveAsTable("interview_prep.bronze_purchase")
)

# 保存件数を確認
purchase_count = spark.table("interview_prep.bronze_purchase").count()
print(f"bronze_purchase 保存完了: {purchase_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーマスター → bronze_user_master
#    日次バッチ想定のため全件上書き・パーティションなし
# ──────────────────────────────────────────────

(
    df_user_master
    .write
    .format("delta")                      # Delta Lake 形式で保存
    .mode("overwrite")                    # 既存テーブルを上書き
    .option("overwriteSchema", "true")    # スキーマ変更も上書き許可
    .saveAsTable("interview_prep.bronze_user_master")
)

# 保存件数を確認
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
