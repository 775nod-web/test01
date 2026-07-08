"""
Bronze layer 保存スクリプト
- sample スキーマのサンプルデータ（顧客マスタ / 口座マスタ / 取引イベント）を
  値を一切変更せずに Bronze layer のテーブルとして保存する
- 追加するのは取り込みメタデータ（取り込み日時 ingested_at ・データソース source_system）のみ
  （既存列の値・型・NULL/表記揺れ等の品質課題はそのまま保持し、加工・クレンジングは行わない）

保存先スキーマ: bronze（存在しない場合は自動作成）
  - bronze.customers
  - bronze.accounts
  - bronze.transactions

前提: sample.bronze_customers / sample.bronze_accounts / sample.bronze_transactions が
      作成済みであること（generate_fraud_sample_data.py を先に実行）
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F

# Databricks ノートブックでは spark はクラスターから自動注入される


# ──────────────────────────────────────────────
# 0. 保存先スキーマ（bronze）の作成
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
print("スキーマ 'bronze' を作成/選択しました")


# ──────────────────────────────────────────────
# 1. サンプルデータ読み込み（sample スキーマ）
#    ※ 以降、既存列に一切の加工（クレンジング・型変換・値の変更）は行わない
# ──────────────────────────────────────────────

df_customers_src = spark.table("sample.bronze_customers")
df_accounts_src = spark.table("sample.bronze_accounts")
df_transactions_src = spark.table("sample.bronze_transactions")


# ──────────────────────────────────────────────
# 2. 取り込みメタデータ列（取り込み日時・データソース）のみを追加
#    既存列はそのまま（withColumnで新規列を追加するのみ）
# ──────────────────────────────────────────────

df_customers_bronze = (
    df_customers_src
    .withColumn("ingested_at", F.current_timestamp())    # 取り込み日時
    .withColumn("source_system", F.lit("customer_master"))  # データソース
)

df_accounts_bronze = (
    df_accounts_src
    .withColumn("ingested_at", F.current_timestamp())
    .withColumn("source_system", F.lit("account_master"))
)

df_transactions_bronze = (
    df_transactions_src
    .withColumn("ingested_at", F.current_timestamp())
    .withColumn("source_system", F.lit("transaction_events"))
)


# ──────────────────────────────────────────────
# 3. Delta テーブルとして bronze スキーマへ保存
# ──────────────────────────────────────────────

(
    df_customers_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.customers")
)

(
    df_accounts_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.accounts")
)

(
    df_transactions_bronze
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.transactions")
)


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== Bronze layer 保存完了 ===")
print("=" * 50)
print(f"  bronze.customers    : {spark.table('bronze.customers').count():>4,} 件")
print(f"  bronze.accounts     : {spark.table('bronze.accounts').count():>4,} 件")
print(f"  bronze.transactions : {spark.table('bronze.transactions').count():>4,} 件")
print("=" * 50)
