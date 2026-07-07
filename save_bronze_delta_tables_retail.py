# Databricks ノートブック用
# generate_retail_pos_sample_data.py で生成済みの DataFrame
# （df_pos / df_products / df_stores / df_customers）を
# Bronze レイヤーの Delta テーブルとして Hive メタストアに保存する
#
# 前提：generate_retail_pos_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("USE bronze")

print("データベース 'bronze' を選択しました")


# ──────────────────────────────────────────────
# 1. POSトランザクション → bronze_pos_transactions
# ──────────────────────────────────────────────

(
    df_pos
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_pos_transactions")
)

pos_count = spark.table("bronze.bronze_pos_transactions").count()
print(f"bronze_pos_transactions 保存完了: {pos_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → bronze_product_master
# ──────────────────────────────────────────────

(
    df_products
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_product_master")
)

product_count = spark.table("bronze.bronze_product_master").count()
print(f"bronze_product_master 保存完了: {product_count:,} 件")


# ──────────────────────────────────────────────
# 3. 店舗マスター → bronze_store_master
# ──────────────────────────────────────────────

(
    df_stores
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_store_master")
)

store_count = spark.table("bronze.bronze_store_master").count()
print(f"bronze_store_master 保存完了: {store_count:,} 件")


# ──────────────────────────────────────────────
# 4. 会員マスター → bronze_customer_master
# ──────────────────────────────────────────────

(
    df_customers
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_customer_master")
)

customer_count = spark.table("bronze.bronze_customer_master").count()
print(f"bronze_customer_master 保存完了: {customer_count:,} 件")


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Bronze レイヤー 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_pos_transactions : {pos_count:>6,} 件")
print(f"  bronze_product_master   : {product_count:>6,} 件")
print(f"  bronze_store_master     : {store_count:>6,} 件")
print(f"  bronze_customer_master  : {customer_count:>6,} 件")
print("=" * 40)


# ──────────────────────────────────────────────
# 6. 保存したテーブルの内容確認（任意）
# ──────────────────────────────────────────────

print("\n=== bronze_pos_transactions 全件 ===")
spark.table("bronze.bronze_pos_transactions").orderBy("transaction_id").show(30, truncate=False)

print("\n=== bronze_product_master 全件 ===")
spark.table("bronze.bronze_product_master").show(truncate=False)

print("\n=== bronze_store_master 全件 ===")
spark.table("bronze.bronze_store_master").show(truncate=False)

print("\n=== bronze_customer_master 全件 ===")
spark.table("bronze.bronze_customer_master").show(truncate=False)
