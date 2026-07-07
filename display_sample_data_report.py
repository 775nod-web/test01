# Databricks ノートブック用
# sample スキーマに保存済みの Bronze サンプルテーブルを読み込み、
#   ・各表のサンプルデータ
#   ・各表の件数
#   ・品質課題データの件数
#   ・意図的に含めた品質課題一覧
# を表示する。
#
# 前提：save_sample_delta_tables.py を実行済みで、以下4表が
#       sample スキーマに保存されていること
#         sample.bronze_pos_transactions
#         sample.bronze_product_master
#         sample.bronze_store_master
#         sample.bronze_customer_master
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）
# ※ 本スクリプトは保存済みテーブルのみを参照するため、事前に df_pos 等の
#   変数がセッションに残っていなくても単独で実行できる。

from pyspark.sql import functions as F

TABLES = {
    "sample.bronze_pos_transactions": "POSトランザクション",
    "sample.bronze_product_master": "商品マスター",
    "sample.bronze_store_master": "店舗マスター",
    "sample.bronze_customer_master": "会員マスター",
}


# ──────────────────────────────────────────────
# 1. 各表のサンプルデータを表示
# ──────────────────────────────────────────────

print("=" * 60)
print("=== 1. 各表のサンプルデータ ===")
print("=" * 60)

for table_name, jp_name in TABLES.items():
    df = spark.table(table_name)
    print(f"\n--- {table_name}（{jp_name}） ---")
    if table_name == "sample.bronze_pos_transactions":
        df.orderBy("transaction_id").show(30, truncate=False)
    else:
        df.show(truncate=False)


# ──────────────────────────────────────────────
# 2. 各表の件数を表示
# ──────────────────────────────────────────────

print("=" * 60)
print("=== 2. 各表の件数 ===")
print("=" * 60)

table_counts = {name: spark.table(name).count() for name in TABLES}
for table_name, jp_name in TABLES.items():
    print(f"{table_name:<32}（{jp_name}）: {table_counts[table_name]:>4,} 件")


# ──────────────────────────────────────────────
# 3. 品質課題データの件数を表示
# ──────────────────────────────────────────────

df_pos = spark.table("sample.bronze_pos_transactions")
df_products = spark.table("sample.bronze_product_master")
df_stores = spark.table("sample.bronze_store_master")

valid_product_ids = [r.product_id for r in df_products.select("product_id").collect()]
valid_store_ids = [r.store_id for r in df_stores.select("store_id").collect()]

# ISO8601 + 日本時間オフセット(+09:00) 形式に一致しないものを「表記揺れ」とみなす
TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$"

dq_checks = [
    ("product_idが商品マスターに存在しない",
     df_pos.filter(~F.col("product_id").isin(valid_product_ids))),
    ("store_idが店舗マスターに存在しない",
     df_pos.filter(~F.col("store_id").isin(valid_store_ids))),
    ("transaction_idの重複",
     df_pos.join(
         df_pos.groupBy("transaction_id").count().filter(F.col("count") > 1).select("transaction_id"),
         on="transaction_id", how="inner",
     )),
    ("quantityが0または負数",
     df_pos.filter(F.col("quantity") <= 0)),
    ("unit_priceがNULLまたは負数",
     df_pos.filter(F.col("unit_price").isNull() | (F.col("unit_price") < 0))),
    ("transaction_timestampの表記が揺れている",
     df_pos.filter(~F.col("transaction_timestamp").rlike(TIMESTAMP_PATTERN))),
    ("customer_idがNULL",
     df_pos.filter(F.col("customer_id").isNull())),
    ("product_categoryがNULL（商品マスター側）",
     df_products.filter(F.col("product_category").isNull())),
]

print("\n" + "=" * 60)
print("=== 3. 品質課題データの件数 ===")
print("=" * 60)
for label, dq_df in dq_checks:
    print(f"[{dq_df.count():>2} 件] {label}")

print("\n--- 品質課題レコード詳細 ---")
for label, dq_df in dq_checks:
    print(f"\n# {label}")
    dq_df.show(truncate=False)


# ──────────────────────────────────────────────
# 4. 意図的に含めた品質課題一覧
# ──────────────────────────────────────────────

INTENTIONAL_DQ_ISSUES = [
    ("1", "product_idが商品マスターに存在しない", 1, "bronze_pos_transactions", "TXN0016（product_id=P999）"),
    ("2", "store_idが店舗マスターに存在しない", 1, "bronze_pos_transactions", "TXN0017（store_id=S999）"),
    ("3", "transaction_idの重複", 2, "bronze_pos_transactions", "TXN0001が2件（同一内容）"),
    ("4", "quantityが0または負数", 2, "bronze_pos_transactions", "TXN0018（0）、TXN0019（-3）"),
    ("5", "unit_priceがNULLまたは負数", 2, "bronze_pos_transactions", "TXN0020（NULL）、TXN0021（-120.0）"),
    ("6", "transaction_timestampの表記揺れ（フォーマット/タイムゾーン）", 2, "bronze_pos_transactions",
     "TXN0022（スラッシュ区切り）、TXN0023（UTC Z表記）"),
    ("7", "customer_idがNULL", 2, "bronze_pos_transactions", "TXN0004、TXN0011"),
    ("8", "product_categoryがNULL", 1, "bronze_product_master", "P006（消しゴム）"),
]

print("\n" + "=" * 60)
print("=== 4. 意図的に含めた品質課題一覧 ===")
print("=" * 60)
print(f"{'No':<4}{'品質課題':<48}{'件数':<6}{'対象表':<28}詳細")
print("-" * 120)
for no, label, count, table, detail in INTENTIONAL_DQ_ISSUES:
    print(f"{no:<4}{label:<48}{count:<6}{table:<28}{detail}")

total_dq_records = sum(c for _, _, c, _, _ in INTENTIONAL_DQ_ISSUES)
print(f"\n品質課題の種類数: {len(INTENTIONAL_DQ_ISSUES)} 種類 / 該当レコード延べ件数: {total_dq_records} 件")
