"""
不正検知データプラットフォーム サンプルデータ 確認スクリプト
- sample スキーマに保存された3表（bronze_customers / bronze_accounts / bronze_transactions）を読み込み
  1. 各表のサンプルデータ
  2. 各表の件数
  3. 品質課題データの件数（カテゴリ別）
  4. 意図的に含めた品質課題一覧
  を表示する

前提: generate_fraud_sample_data.py を同セッションで実行済み、または
      sample スキーマに対象テーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark.sql("USE sample")

df_customers = spark.table("sample.bronze_customers")
df_accounts = spark.table("sample.bronze_accounts")
df_transactions = spark.table("sample.bronze_transactions")


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータ表示
# ──────────────────────────────────────────────

print("=" * 60)
print("1. 各表のサンプルデータ")
print("=" * 60)

print("\n--- bronze_customers ---")
df_customers.orderBy("customer_id").show(truncate=False)

print("\n--- bronze_accounts ---")
df_accounts.orderBy("account_id").show(truncate=False)

print("\n--- bronze_transactions ---")
df_transactions.orderBy("transaction_id").show(40, truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数
# ──────────────────────────────────────────────

customers_total = df_customers.count()
accounts_total = df_accounts.count()
transactions_total = df_transactions.count()

print("\n" + "=" * 60)
print("2. 各表の件数")
print("=" * 60)
print(f"  bronze_customers    : {customers_total:>4,} 件")
print(f"  bronze_accounts     : {accounts_total:>4,} 件")
print(f"  bronze_transactions : {transactions_total:>4,} 件")


# ──────────────────────────────────────────────
# 3. 品質課題データの件数（カテゴリ別）
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("3. 品質課題データの件数（bronze_transactions）")
print("=" * 60)

# (a) transaction_id の重複
dup_groups = (
    df_transactions.groupBy("transaction_id").count().filter(F.col("count") > 1)
)
dup_group_count = dup_groups.count()
dup_row_count = dup_groups.agg(F.sum("count")).collect()[0][0] or 0
print(f"\n(a) transaction_id 重複        : {dup_group_count} 種類 / 対象 {dup_row_count} レコード")
dup_groups.show(truncate=False)

# (b) customer_id が顧客マスタに不一致
orphan_customer = df_transactions.join(
    df_customers.select("customer_id"), on="customer_id", how="left_anti"
)
orphan_customer_count = orphan_customer.count()
print(f"\n(b) customer_id 不一致（顧客マスタに存在しない） : {orphan_customer_count} レコード")
orphan_customer.select("transaction_id", "customer_id").show(truncate=False)

# (c) account_id が口座マスタに不一致
orphan_account = df_transactions.join(
    df_accounts.select("account_id"), on="account_id", how="left_anti"
)
orphan_account_count = orphan_account.count()
print(f"\n(c) account_id 不一致（口座マスタに存在しない）  : {orphan_account_count} レコード")
orphan_account.select("transaction_id", "account_id").show(truncate=False)

# (d) 金額異常（0円・マイナス）
invalid_amount = df_transactions.filter(F.col("amount") <= 0)
invalid_amount_count = invalid_amount.count()
print(f"\n(d) 金額異常（0円・マイナス）  : {invalid_amount_count} レコード")
invalid_amount.select("transaction_id", "amount").show(truncate=False)

# (e) タイムスタンプ形式・タイムゾーン揺れ
#     正規形式: yyyy-MM-ddTHH:mm:ss+09:00 以外を揺れとみなす
CANONICAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
ts_variant = df_transactions.filter(~F.col("transaction_ts").rlike(CANONICAL_TS_PATTERN))
ts_variant_count = ts_variant.count()
print(f"\n(e) タイムスタンプ形式・タイムゾーン揺れ        : {ts_variant_count} レコード")
ts_variant.select("transaction_id", "transaction_ts").show(truncate=False)

# (f) カントリーコード表記揺れ（日本を表す値が正規形式 "JP" 以外で表記されているケースを検出）
country_variant = df_transactions.filter(
    F.col("country_code").isNotNull()
    & (F.upper(F.trim(F.col("country_code"))).isin("JP", "JAPAN", "JPN"))
    & (F.col("country_code") != "JP")
)
country_variant_count = country_variant.count()
print(f"\n(f) カントリーコード表記揺れ    : {country_variant_count} レコード")
country_variant.select("transaction_id", "country_code").show(truncate=False)

# (g) 加盟店カテゴリの NULL・表記揺れ
#     正規カテゴリ一覧
VALID_CATEGORIES = ["Grocery", "Restaurant", "Electronics", "Travel", "Utilities", "Entertainment"]
#     ATM/出金取引は merchant_category が NULL でも正当（業務ルール）
category_null_issue = df_transactions.filter(
    F.col("merchant_category").isNull() & (~F.col("transaction_type").isin("atm", "withdrawal"))
)
category_variant_issue = df_transactions.filter(
    F.col("merchant_category").isNotNull() & (~F.col("merchant_category").isin(VALID_CATEGORIES))
)
category_issue_count = category_null_issue.count() + category_variant_issue.count()
print(f"\n(g) 加盟店カテゴリ NULL・表記揺れ（業務上正当なATM/出金のNULLは除外） : {category_issue_count} レコード")
category_null_issue.select("transaction_id", "transaction_type", "merchant_category").show(truncate=False)
category_variant_issue.select("transaction_id", "transaction_type", "merchant_category").show(truncate=False)

# (h) fraud_label が NULL
fraud_label_null_count = df_transactions.filter(F.col("fraud_label").isNull()).count()
fraud_label_null_ratio = fraud_label_null_count / transactions_total * 100
print(f"\n(h) fraud_label が NULL         : {fraud_label_null_count} / {transactions_total} レコード（{fraud_label_null_ratio:.1f}%）")

# (i) 同一顧客の短時間複数取引（バーストパターン, 15分以内の連続取引）
#     正規形式のタイムスタンプのみパースして時系列で比較する
#     ANSIモード（Databricksのデフォルト）では to_timestamp は形式不一致の値に対して
#     例外を送出するため、形式不一致をNULLとして許容する try_to_timestamp を使用する
w = Window.partitionBy("customer_id").orderBy("parsed_ts")
df_parsed = (
    df_transactions
    .withColumn(
        "parsed_ts",
        F.try_to_timestamp("transaction_ts", F.lit("yyyy-MM-dd'T'HH:mm:ssXXX")),
    )
    .filter(F.col("parsed_ts").isNotNull())
    .withColumn("prev_ts", F.lag("parsed_ts").over(w))
    .withColumn("prev_transaction_id", F.lag("transaction_id").over(w))
    .withColumn("gap_seconds", F.col("parsed_ts").cast("long") - F.col("prev_ts").cast("long"))
)
# 同一 transaction_id の重複行同士（gap=0）は「重複」課題であり「バースト」ではないため除外する
burst_pairs = df_parsed.filter(
    F.col("gap_seconds").isNotNull()
    & (F.col("gap_seconds") <= 900)
    & (F.col("transaction_id") != F.col("prev_transaction_id"))
)
burst_transaction_ids = (
    burst_pairs.select(F.col("transaction_id").alias("tx_id"))
    .union(burst_pairs.select(F.col("prev_transaction_id").alias("tx_id")))
    .distinct()
)
burst_customers = burst_pairs.select("customer_id").distinct()
burst_count = burst_transaction_ids.count()
print(f"\n(i) 同一顧客の短時間（15分以内）複数取引（バーストパターン） : "
      f"対象顧客 {burst_customers.count()} 名 / {burst_count} レコード")
burst_customers.show(truncate=False)
burst_transaction_ids.orderBy("tx_id").show(truncate=False)

structural_issue_count = (
    dup_row_count + orphan_customer_count + orphan_account_count
    + invalid_amount_count + ts_variant_count + country_variant_count + category_issue_count
)
print(f"\n構造的な品質課題を持つレコード合計（重複/マスタ不一致/金額異常/形式揺れ）: "
      f"{structural_issue_count} / {transactions_total} レコード")


# ──────────────────────────────────────────────
# 4. 意図的に含めた品質課題一覧
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("4. 意図的に含めた品質課題一覧（bronze_transactions）")
print("=" * 60)

quality_issue_summary = [
    ("transaction_idの重複",                          f"{dup_group_count}種類 / {dup_row_count}レコード"),
    ("customer_idが顧客マスタに不一致",                 f"{orphan_customer_count}レコード"),
    ("account_idが口座マスタに不一致",                  f"{orphan_account_count}レコード"),
    ("金額異常（0円・マイナス）",                        f"{invalid_amount_count}レコード"),
    ("タイムスタンプ形式・タイムゾーン揺れ",              f"{ts_variant_count}レコード"),
    ("カントリーコード表記揺れ（JP/Japan/JPN/jp等）",     f"{country_variant_count}レコード"),
    ("加盟店カテゴリのNULL・表記揺れ",                    f"{category_issue_count}レコード"),
    ("fraud_labelがNULL（ラベル不足）",                  f"{fraud_label_null_count}レコード（{fraud_label_null_ratio:.1f}%）"),
    ("同一顧客の短時間複数取引（バーストパターン）",       f"対象顧客{burst_customers.count()}名 / {burst_count}レコード"),
]

summary_schema = ["品質課題", "件数"]
df_summary = spark.createDataFrame(quality_issue_summary, schema=summary_schema)
df_summary.show(truncate=False)
