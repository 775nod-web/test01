"""
Bronze layer データ確認スクリプト
- bronze スキーマの3表（customers / accounts / transactions）を読み込み、
  1. 各表のデータ
  2. 各表の件数
  を表示する

前提: save_bronze_layer_tables.py を先に実行し、bronze スキーマにテーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

spark.sql("USE bronze")

df_customers = spark.table("bronze.customers")
df_accounts = spark.table("bronze.accounts")
df_transactions = spark.table("bronze.transactions")


# ──────────────────────────────────────────────
# 1. 各表のデータ表示
# ──────────────────────────────────────────────

print("=" * 60)
print("1. Bronze layer 表データ")
print("=" * 60)

print("\n--- bronze.customers ---")
df_customers.orderBy("customer_id").show(truncate=False)

print("\n--- bronze.accounts ---")
df_accounts.orderBy("account_id").show(truncate=False)

print("\n--- bronze.transactions ---")
df_transactions.orderBy("transaction_id").show(40, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("2. Bronze layer 表件数")
print("=" * 60)
print(f"  bronze.customers    : {df_customers.count():>4,} 件")
print(f"  bronze.accounts     : {df_accounts.count():>4,} 件")
print(f"  bronze.transactions : {df_transactions.count():>4,} 件")
print("=" * 60)
