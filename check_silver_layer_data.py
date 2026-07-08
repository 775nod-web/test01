"""
Silver layer データ確認スクリプト
- silver スキーマの3表（customers / accounts / transactions）を読み込み、
  1. 各表のデータ
  2. 各表の件数
  を表示する

前提: save_silver_layer_tables.py を先に実行し、silver スキーマにテーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

spark.sql("USE silver")

df_customers = spark.table("silver.customers")
df_accounts = spark.table("silver.accounts")
df_transactions = spark.table("silver.transactions")


# ──────────────────────────────────────────────
# 1. 各表のデータ表示
# ──────────────────────────────────────────────

print("=" * 60)
print("1. Silver layer 表データ")
print("=" * 60)

print("\n--- silver.customers ---")
df_customers.orderBy("customer_id").show(truncate=False)

print("\n--- silver.accounts ---")
df_accounts.orderBy("account_id").show(truncate=False)

print("\n--- silver.transactions ---")
df_transactions.orderBy("transaction_id").show(40, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("2. Silver layer 表件数")
print("=" * 60)
print(f"  silver.customers    : {df_customers.count():>4,} 件")
print(f"  silver.accounts     : {df_accounts.count():>4,} 件")
print(f"  silver.transactions : {df_transactions.count():>4,} 件")
print("=" * 60)
