"""
Silver layer 品質チェックスクリプト
- bronze.transactions（クレンジング前）と silver.transactions（クレンジング後）を比較し、
  Knowledge baseで定義された9種類の品質課題がSilverで意図通りに解消・可視化されているかを検証する
- あわせて、Gold layer（fraud daily kpi / 疑わしいトランザクションリスト /
  顧客単位のリスク / データ品質サマリー）の算出に必要な列がSilverに揃っているかも確認する

前提: save_silver_layer_tables.py が実行済みで bronze / silver 両スキーマに
      テーブルが作成済みであること
動作確認環境: Databricks Free Edition
"""

from pyspark.sql import functions as F

df_bronze_tx = spark.table("bronze.transactions")
df_silver_tx = spark.table("silver.transactions")
df_silver_cust = spark.table("silver.customers")
df_silver_acct = spark.table("silver.accounts")

VALID_CATEGORIES = ["Grocery", "Restaurant", "Electronics", "Travel", "Utilities", "Entertainment"]

check_results = []  # (category, detail, passed)


def record(category, detail, passed):
    check_results.append((category, detail, passed))
    print(f"  [{'OK' if passed else 'NG'}] {detail}")


# ──────────────────────────────────────────────
# 1. 重複除去のチェック
# ──────────────────────────────────────────────

print("=" * 70)
print("(1) transaction_id 重複")
print("=" * 70)

bronze_dup_groups = df_bronze_tx.groupBy("transaction_id").count().filter(F.col("count") > 1)
bronze_dup_row_count = bronze_dup_groups.agg(F.sum("count")).collect()[0][0] or 0
silver_dup_groups = df_silver_tx.groupBy("transaction_id").count().filter(F.col("count") > 1)

print(f"  Bronze: 重複ID {bronze_dup_groups.count()}種 / 対象{bronze_dup_row_count}レコード")
print(f"  Silver: 重複ID {silver_dup_groups.count()}種 / 総件数 {df_silver_tx.count()}件"
      f"（Bronze {df_bronze_tx.count()}件から{df_bronze_tx.count() - df_silver_tx.count()}件削減）")
record("重複除去", "Silverに重複transaction_idが残っていない", silver_dup_groups.count() == 0)


# ──────────────────────────────────────────────
# 2. customer_id マスタ不一致のチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(2) customer_id マスタ不一致")
print("=" * 70)

bronze_orphan_customer = df_bronze_tx.join(
    df_silver_cust.select("customer_id"), "customer_id", "left_anti"
).count()
silver_flagged_invalid_customer = df_silver_tx.filter(~F.col("is_customer_valid")).count()

print(f"  Bronze時点の不一致取引数         : {bronze_orphan_customer}件")
print(f"  Silverで is_customer_valid=false : {silver_flagged_invalid_customer}件")
record(
    "customer_id不一致の可視化",
    "is_customer_validフラグが不一致取引を過不足なく検知し、行を削除せず保持している",
    silver_flagged_invalid_customer == bronze_orphan_customer and silver_flagged_invalid_customer > 0,
)


# ──────────────────────────────────────────────
# 3. account_id マスタ不一致のチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(3) account_id マスタ不一致")
print("=" * 70)

bronze_orphan_account = df_bronze_tx.join(
    df_silver_acct.select("account_id"), "account_id", "left_anti"
).count()
silver_flagged_invalid_account = df_silver_tx.filter(~F.col("is_account_valid")).count()

print(f"  Bronze時点の不一致取引数        : {bronze_orphan_account}件")
print(f"  Silverで is_account_valid=false : {silver_flagged_invalid_account}件")
record(
    "account_id不一致の可視化",
    "is_account_validフラグが不一致取引を過不足なく検知し、行を削除せず保持している",
    silver_flagged_invalid_account == bronze_orphan_account and silver_flagged_invalid_account > 0,
)


# ──────────────────────────────────────────────
# 4. 金額異常のチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(4) 金額異常（0円・マイナス）")
print("=" * 70)

bronze_invalid_amount = df_bronze_tx.filter(F.col("amount") <= 0).count()
silver_flagged_invalid_amount = df_silver_tx.filter(~F.col("is_amount_valid")).count()
silver_amount_rows_retained = df_silver_tx.filter(~F.col("is_amount_valid")).select("transaction_id").count()

print(f"  Bronze時点の金額異常件数        : {bronze_invalid_amount}件")
print(f"  Silverで is_amount_valid=false  : {silver_flagged_invalid_amount}件")
record(
    "金額異常の可視化",
    "is_amount_validフラグが金額異常取引を過不足なく検知し、行を削除せず保持している",
    silver_flagged_invalid_amount == bronze_invalid_amount and silver_amount_rows_retained > 0,
)


# ──────────────────────────────────────────────
# 5. タイムスタンプ形式・タイムゾーン揺れのチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(5) タイムスタンプ形式・タイムゾーン揺れ")
print("=" * 70)

CANONICAL_TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
bronze_ts_variant = df_bronze_tx.filter(~F.col("transaction_ts").rlike(CANONICAL_TS_PATTERN)).count()
silver_ts_unparsed = df_silver_tx.filter(~F.col("is_timestamp_valid")).count()

print(f"  Bronze時点の形式揺れ件数           : {bronze_ts_variant}件")
print(f"  Silverで is_timestamp_valid=false  : {silver_ts_unparsed}件（標準化後もパースできなかった件数）")
record(
    "タイムスタンプ標準化",
    "全パターンが正しくパースされ、is_timestamp_valid=falseの残存が0件",
    silver_ts_unparsed == 0,
)


# ──────────────────────────────────────────────
# 6. カントリーコード表記揺れのチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(6) カントリーコード表記揺れ")
print("=" * 70)

non_canonical_country = df_silver_tx.filter(
    F.col("country_code").isNotNull() & ~F.col("country_code").rlike(r"^[A-Z]{2}$")
).count()
japan_variants_normalized = df_silver_tx.filter(
    (F.col("country_code_raw") != "JP") & F.col("country_code_raw").rlike(r"(?i)^\s*(japan|jpn|jp)\s*$")
).filter(F.col("country_code") == "JP").count()
japan_variants_total = df_silver_tx.filter(
    (F.col("country_code_raw") != "JP") & F.col("country_code_raw").rlike(r"(?i)^\s*(japan|jpn|jp)\s*$")
).count()

print(f"  正規形式(2桁大文字)以外が残っている件数 : {non_canonical_country}件")
print(f"  日本表記揺れ -> JPに正規化できた件数     : {japan_variants_normalized} / {japan_variants_total}件")
record(
    "カントリーコード正規化",
    "全ての国コードが2桁大文字に正規化され、日本の表記揺れが全てJPに統一されている",
    non_canonical_country == 0 and japan_variants_normalized == japan_variants_total and japan_variants_total > 0,
)


# ──────────────────────────────────────────────
# 7. 加盟店カテゴリ NULL・表記揺れのチェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(7) 加盟店カテゴリ NULL・表記揺れ")
print("=" * 70)

non_canonical_category = df_silver_tx.filter(
    F.col("merchant_category").isNotNull() & (~F.col("merchant_category").isin(VALID_CATEGORIES))
).count()
casing_variants_fixed = df_silver_tx.filter(
    (F.col("merchant_category_raw") != F.col("merchant_category"))
    & F.col("merchant_category_raw").isNotNull()
    & F.col("merchant_category").isNotNull()
).count()
legit_null_still_valid = df_silver_tx.filter(
    F.col("transaction_type").isin("atm", "withdrawal") & F.col("merchant_category_raw").isNull()
).filter(F.col("is_category_valid")).count()
legit_null_total = df_silver_tx.filter(
    F.col("transaction_type").isin("atm", "withdrawal") & F.col("merchant_category_raw").isNull()
).count()
unresolved_kept_as_null = df_silver_tx.filter(
    F.col("merchant_category_raw").isNotNull()
    & (~F.col("transaction_type").isin("atm", "withdrawal"))
    & F.col("merchant_category").isNull()
    & (~F.col("is_category_valid"))
).count()

print(f"  正規カテゴリ以外が残っている件数         : {non_canonical_category}件")
print(f"  大文字小文字等の表記揺れを正規化できた件数 : {casing_variants_fixed}件")
print(f"  ATM/出金の正当なNULLをvalid判定できた件数  : {legit_null_still_valid} / {legit_null_total}件")
print(f"  マッピング不能な値を誤補正せずNULL+invalid継続 : {unresolved_kept_as_null}件")
record(
    "加盟店カテゴリ正規化",
    "表記揺れは正規化・ATM等の正当なNULLはvalid・マッピング不能値は誤補正せずinvalidのまま",
    non_canonical_category == 0
    and casing_variants_fixed > 0
    and legit_null_still_valid == legit_null_total
    and unresolved_kept_as_null > 0,
)


# ──────────────────────────────────────────────
# 8. fraud_label がNULLの取引が多い（Silverでは補完せず保持）
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(8) fraud_label（Silverで値を補完・改変していないか）")
print("=" * 70)

# 重複除去された行はいずれもfraud_label=NULLだったため、Silverのnull件数は
# Bronzeのnull件数から重複除去件数を差し引いた値と一致するはずである
bronze_label_null = df_bronze_tx.filter(F.col("fraud_label").isNull()).count()
silver_label_null = df_silver_tx.filter(F.col("fraud_label").isNull()).count()
removed_by_dedup = df_bronze_tx.count() - df_silver_tx.count()

print(f"  Bronzeでのfraud_label NULL件数 : {bronze_label_null}件")
print(f"  Silverでのfraud_label NULL件数 : {silver_label_null}件（重複除去分を除き値の改変なし）")
record(
    "fraud_labelの非改変",
    "Silverはfraud_labelを補完・削除せず、重複除去分のみ件数が変動している",
    silver_label_null == bronze_label_null - removed_by_dedup,
)


# ──────────────────────────────────────────────
# 9. 同一顧客の短時間複数取引（バーストパターン）
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(9) 同一顧客の短時間複数取引（バーストパターン）")
print("=" * 70)

burst_flagged = df_silver_tx.filter(F.col("is_rapid_succession"))
burst_customers = burst_flagged.select("customer_id").distinct()

print(f"  is_rapid_succession=true の件数 : {burst_flagged.count()}件")
burst_customers.show(truncate=False)
record(
    "バーストパターン検知",
    "is_rapid_succession特徴量が短時間連続取引を検知している",
    burst_flagged.count() > 0,
)


# ──────────────────────────────────────────────
# 10. Gold layer 要件充足チェック
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("(10) Gold layer 算出に必要な列の充足チェック")
print("=" * 70)

gold_requirements = {
    "fraud daily kpi（日次件数/総額/高リスク件数/不正疑い率/平均リスクスコア）": [
        ("silver.transactions", df_silver_tx, ["transaction_timestamp", "amount", "fraud_label",
                                                "is_amount_valid", "is_customer_valid", "is_account_valid"]),
    ],
    "疑わしいトランザクションリスト（ID/顧客ID/金額/理由）": [
        ("silver.transactions", df_silver_tx, ["transaction_id", "customer_id", "amount",
                                                "is_amount_valid", "is_customer_valid", "is_account_valid",
                                                "is_category_valid", "is_rapid_succession", "fraud_label"]),
    ],
    "顧客単位のリスク（件数/総額/深夜取引/海外取引/リスクレベル）": [
        ("silver.transactions", df_silver_tx, ["customer_id", "amount", "transaction_timestamp", "country_code"]),
        ("silver.customers", df_silver_cust, ["customer_id", "residence_country", "risk_category"]),
    ],
    "データ品質サマリー（重複/不一致/異常/揺れの件数）": [
        ("silver.transactions", df_silver_tx, ["is_customer_valid", "is_account_valid", "is_amount_valid",
                                                "is_timestamp_valid", "is_category_valid"]),
    ],
}

for gold_output, table_checks in gold_requirements.items():
    print(f"\n  ■ {gold_output}")
    all_ok = True
    for table_name, df, required_columns in table_checks:
        missing = [c for c in required_columns if c not in df.columns]
        ok = len(missing) == 0
        all_ok = all_ok and ok
        print(f"    [{'OK' if ok else 'NG'}] {table_name}: "
              f"{'必要列は全て存在' if ok else f'不足列={missing}'}")
    record(f"Gold要件充足: {gold_output}", "算出に必要な列が揃っている", all_ok)


# ──────────────────────────────────────────────
# 総合結果
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
print("品質チェック 総合結果")
print("=" * 70)
for category, detail, passed in check_results:
    print(f"  [{'PASS' if passed else 'FAIL'}] {category}")

overall_passed = all(passed for _, _, passed in check_results)
print("=" * 70)
print(f"最終判定: {'全項目 PASS（Silver layerで品質課題が意図通り解消・可視化されている）' if overall_passed else '一部 FAIL（要確認）'}")
print("=" * 70)
