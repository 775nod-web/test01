# Databricks ノートブック用
# generate_retail_pos_sample_data.py で生成済みの DataFrame
# （df_pos / df_products / df_stores / df_customers）を
# サンプルデータ用スキーマ「sample」に Delta テーブルとして保存する
#
# 前提：generate_retail_pos_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）
#
# 保存先：sample スキーマ（存在しない場合は自動作成）
#   sample.bronze_pos_transactions   … POSトランザクション
#   sample.bronze_product_master     … 商品マスター
#   sample.bronze_store_master       … 店舗マスター
#   sample.bronze_customer_master    … 会員マスター
# テーブル名に "bronze_" を付与しているのは、メダリオンアーキテクチャの
# Bronzeレイヤー（生データ）である位置付けを明示するため。

# ──────────────────────────────────────────────
# 0. 保存先スキーマ「sample」の作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS sample")
spark.sql("USE sample")

print("スキーマ 'sample' を選択しました（存在しない場合は作成済み）")


# ──────────────────────────────────────────────
# 1. POSトランザクション → sample.bronze_pos_transactions
# ──────────────────────────────────────────────

(
    df_pos
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_pos_transactions")
)

pos_count = spark.table("sample.bronze_pos_transactions").count()
print(f"sample.bronze_pos_transactions 保存完了: {pos_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → sample.bronze_product_master
# ──────────────────────────────────────────────

(
    df_products
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_product_master")
)

product_count = spark.table("sample.bronze_product_master").count()
print(f"sample.bronze_product_master 保存完了: {product_count:,} 件")


# ──────────────────────────────────────────────
# 3. 店舗マスター → sample.bronze_store_master
# ──────────────────────────────────────────────

(
    df_stores
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_store_master")
)

store_count = spark.table("sample.bronze_store_master").count()
print(f"sample.bronze_store_master 保存完了: {store_count:,} 件")


# ──────────────────────────────────────────────
# 4. 会員マスター → sample.bronze_customer_master
# ──────────────────────────────────────────────

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.bronze_customer_master")
)

customer_count = spark.table("sample.bronze_customer_master").count()
print(f"sample.bronze_customer_master 保存完了: {customer_count:,} 件")


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== sample スキーマ 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_pos_transactions : {pos_count:>6,} 件")
print(f"  bronze_product_master   : {product_count:>6,} 件")
print(f"  bronze_store_master     : {store_count:>6,} 件")
print(f"  bronze_customer_master  : {customer_count:>6,} 件")
print("=" * 40)


# ──────────────────────────────────────────────
# 6. 保存したテーブルの内容確認（任意）
# ──────────────────────────────────────────────

print("\n=== sample.bronze_pos_transactions 全件 ===")
spark.table("sample.bronze_pos_transactions").orderBy("transaction_id").show(30, truncate=False)

print("\n=== sample.bronze_product_master 全件 ===")
spark.table("sample.bronze_product_master").show(truncate=False)

print("\n=== sample.bronze_store_master 全件 ===")
spark.table("sample.bronze_store_master").show(truncate=False)

print("\n=== sample.bronze_customer_master 全件 ===")
spark.table("sample.bronze_customer_master").show(truncate=False)
