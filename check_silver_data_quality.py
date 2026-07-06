# Databricks ノートブック用
# Silverレイヤーの品質チェック
#
# 前提：save_bronze01_tables.py と save_silver_tables.py を
#       同セッションで実行済みであること
#
# 目的：
#   Knowledge baseに列挙された品質課題（user_id null/マスター不一致、event_id重複、
#   payment_dateのフォーマット揺れ、amountの0/負値、payment_statusの想定外の値、
#   イベントの遅延到着、country_codeの表記揺れ）が、Gold layerの表設計
#   （gold_daily_kpi / gold_at_risk_users / gold_data_quality_summary / gold_user_ml_features）
#   で安全に使える形までクレンジングできているかを検証する。
#
# 検証方針：
#   (a) 修正できるはずの課題は「もう残っていないこと」を確認する
#       （country_code表記揺れ、payment_dateパース失敗、event_id重複）
#   (b) 修正できない課題は「is_valid_for_gold=Falseとして正しく除外されていること」を確認する
#       （user_idのnull/マスター不一致、amountの0/負値、payment_statusの想定外の値）
#   (c) is_valid_for_gold=Trueのレコードが実際にGold集計に使える品質かをクロスチェックする
#       （フラグが不当にTrueになっている「見逃し」が無いかを確認する）

from pyspark.sql import functions as F

BRONZE_SCHEMA = "bronze01"
SILVER_SCHEMA = "silver"

VALID_PAYMENT_STATUSES = ["success", "failed", "pending", "refunded"]
KNOWN_COUNTRY_CODES = ["JP", "US", "GB", "DE", "FR", "IN", "BR", "AU", "KR", "CA"]

check_results = []  # (check_name, passed: bool, detail: str)


def record_check(name, passed, detail):
    check_results.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name} — {detail}")


print("=" * 70)
print("Silverレイヤー 品質チェック")
print("=" * 70)


# ──────────────────────────────────────────────
# 1. silver_users
# ──────────────────────────────────────────────

print("\n--- silver_users ---")
df_su = spark.table(f"{SILVER_SCHEMA}.silver_users")

bad_country_remaining = df_su.filter(~F.col("country_code").isin(KNOWN_COUNTRY_CODES)).count()
record_check(
    "country_codeの表記揺れが解消されている",
    bad_country_remaining == 0,
    f"既知の正規コード以外が残っている件数: {bad_country_remaining} 件（期待値: 0）",
)

corrected_country_count = df_su.filter(F.col("dq_issues") == "country_code_variant_corrected").count()
print(f"country_code表記揺れを補正した件数: {corrected_country_count} 件")

invalid_users = df_su.filter("is_valid_for_gold = false").count()
record_check(
    "silver_usersは全件がGold集計に使用可能",
    invalid_users == 0,
    f"is_valid_for_gold=False の件数: {invalid_users} 件（期待値: 0、user masterに回復不能な課題は無いため）",
)


# ──────────────────────────────────────────────
# 2. silver_subscriptions
# ──────────────────────────────────────────────

print("\n--- silver_subscriptions ---")
df_ss = spark.table(f"{SILVER_SCHEMA}.silver_subscriptions")

unparseable_dates = df_ss.filter(F.col("payment_date").isNull()).count()
record_check(
    "payment_dateのフォーマット揺れが解消され、全件DATE型で解析できている",
    unparseable_dates == 0,
    f"payment_dateがNULL（解析失敗）の件数: {unparseable_dates} 件（期待値: 0）",
)

out_of_domain_status = df_ss.filter(~F.col("payment_status").isin(VALID_PAYMENT_STATUSES + ["unknown"])).count()
record_check(
    "payment_statusが正規値(success/failed/pending/refunded)または'unknown'に正規化されている",
    out_of_domain_status == 0,
    f"正規化できていない値の件数: {out_of_domain_status} 件（期待値: 0）",
)

# is_valid_for_gold=Falseのレコードには必ず理由(dq_issues)が付与されているか
invalid_without_reason = df_ss.filter(
    (F.col("is_valid_for_gold") == False) & (F.col("dq_issues").isNull() | (F.col("dq_issues") == ""))
).count()
record_check(
    "Gold除外レコードには必ず除外理由(dq_issues)が記録されている",
    invalid_without_reason == 0,
    f"理由未記録の件数: {invalid_without_reason} 件（期待値: 0）",
)

# is_valid_for_gold=True のレコードが実際にクリーンかをクロスチェック（フラグの見逃しが無いか）
false_positive_valid = df_ss.filter(
    (F.col("is_valid_for_gold") == True)
    & (
        F.col("user_id").isNull()
        | (F.col("amount") <= 0)
        | (~F.col("payment_status").isin(VALID_PAYMENT_STATUSES))
        | F.col("payment_date").isNull()
    )
).count()
record_check(
    "is_valid_for_gold=Trueのレコードに品質課題の見逃しが無い",
    false_positive_valid == 0,
    f"Trueなのに課題が残っている件数: {false_positive_valid} 件（期待値: 0）",
)

valid_sub_count = df_ss.filter("is_valid_for_gold = true").count()
invalid_sub_count = df_ss.filter("is_valid_for_gold = false").count()
print(f"Gold集計に使用可能: {valid_sub_count} 件 / 除外: {invalid_sub_count} 件（総件数: {df_ss.count()} 件）")
print("除外理由の内訳:")
df_ss.filter("is_valid_for_gold = false").groupBy("dq_issues").count().orderBy(F.desc("count")).show(truncate=False)


# ──────────────────────────────────────────────
# 3. silver_user_events
# ──────────────────────────────────────────────

print("\n--- silver_user_events ---")
df_se = spark.table(f"{SILVER_SCHEMA}.silver_user_events")

total_events = df_se.count()
distinct_event_ids = df_se.select("event_id").distinct().count()
record_check(
    "event_idの重複到着が解消されている（重複排除後は一意）",
    total_events == distinct_event_ids,
    f"総件数: {total_events} 件 / ユニークevent_id数: {distinct_event_ids} 件",
)

bronze_events_count = spark.table(f"{BRONZE_SCHEMA}.bronze_user_events").count()
print(f"bronze_user_events件数: {bronze_events_count} 件 → silver_user_events件数: {total_events} 件"
      f"（重複排除で {bronze_events_count - total_events} 件減）")

false_positive_events = df_se.filter(
    (F.col("is_valid_for_gold") == True) & (F.col("user_id").isNull())
).count()
record_check(
    "is_valid_for_gold=Trueのイベントに未解決のuser_id欠損が無い",
    false_positive_events == 0,
    f"Trueなのにuser_idが欠損している件数: {false_positive_events} 件（期待値: 0）",
)

# user masterに存在しないuser_idが、is_valid_for_gold=Trueに紛れ込んでいないか
valid_user_ids = [r.user_id for r in spark.table(f"{SILVER_SCHEMA}.silver_users").select("user_id").collect()]
orphan_in_valid = df_se.filter(
    (F.col("is_valid_for_gold") == True)
    & F.col("user_id").isNotNull()
    & (~F.col("user_id").isin(valid_user_ids))
).count()
record_check(
    "is_valid_for_gold=Trueのイベントに未解決のuser_idマスター不一致が無い",
    orphan_in_valid == 0,
    f"Trueなのにマスター不一致が残っている件数: {orphan_in_valid} 件（期待値: 0）",
)

valid_evt_count = df_se.filter("is_valid_for_gold = true").count()
invalid_evt_count = df_se.filter("is_valid_for_gold = false").count()
delayed_count = df_se.filter("is_delayed_arrival = true").count()
print(f"Gold集計に使用可能: {valid_evt_count} 件 / 除外: {invalid_evt_count} 件（総件数: {total_events} 件）")
print(f"遅延到着（参考情報。除外はしない）: {delayed_count} 件")


# ──────────────────────────────────────────────
# 4. 総合結果
# ──────────────────────────────────────────────

print("\n" + "=" * 70)
all_passed = all(passed for _, passed, _ in check_results)
passed_count = sum(1 for _, passed, _ in check_results if passed)
print(f"=== 品質チェック結果: {passed_count}/{len(check_results)} 件PASS ===")
if all_passed:
    print("=== 総合判定: 全チェックPASS（Gold layerでの集計に利用できる品質になっている） ===")
else:
    print("=== 総合判定: FAILあり。上記チェック結果を確認してください ===")
print("=" * 70)
