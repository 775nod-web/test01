"""
Gold layer データ確認スクリプト
- gold スキーマの4表（fraud_daily_kpi / suspicious_transactions / customer_risk /
  data_quality_summary）を読み込み、
  1. 各表のデータ
  2. 各表の件数
  を表示する

前提: save_gold_layer_tables.py を先に実行し、gold スキーマにテーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

spark.sql("USE gold")

df_fraud_daily_kpi = spark.table("gold.fraud_daily_kpi")
df_suspicious_transactions = spark.table("gold.suspicious_transactions")
df_customer_risk = spark.table("gold.customer_risk")
df_data_quality_summary = spark.table("gold.data_quality_summary")


# ──────────────────────────────────────────────
# 1. 各表のデータ表示
# ──────────────────────────────────────────────

print("=" * 60)
print("1. Gold layer 表データ")
print("=" * 60)

print("\n--- gold.fraud_daily_kpi ---")
df_fraud_daily_kpi.orderBy("transaction_date").show(truncate=False)

print("\n--- gold.suspicious_transactions ---")
df_suspicious_transactions.orderBy(df_suspicious_transactions.risk_score.desc()).show(40, truncate=False)

print("\n--- gold.customer_risk ---")
df_customer_risk.orderBy(df_customer_risk.high_risk_transaction_count.desc()).show(truncate=False)

print("\n--- gold.data_quality_summary ---")
df_data_quality_summary.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("2. Gold layer 表件数")
print("=" * 60)
print(f"  gold.fraud_daily_kpi         : {df_fraud_daily_kpi.count():>4,} 件")
print(f"  gold.suspicious_transactions : {df_suspicious_transactions.count():>4,} 件")
print(f"  gold.customer_risk           : {df_customer_risk.count():>4,} 件")
print(f"  gold.data_quality_summary    : {df_data_quality_summary.count():>4,} 件")
print("=" * 60)
