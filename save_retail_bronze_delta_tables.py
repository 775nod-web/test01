# Databricks ノートブック用
# 生成済み DataFrame（df_stores / df_products / df_customers / df_transactions）を
# Bronze レイヤーの Delta テーブルとして Hive メタストアに保存する
#
# 前提：generate_retail_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("USE bronze")

print("データベース 'bronze' を選択しました")


# ──────────────────────────────────────────────
# 1. 店舗マスター → bronze_store_master
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
# 3. 顧客/会員データ → bronze_customer_master
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
# 4. POS売上イベント → bronze_pos_sales_transactions
# ──────────────────────────────────────────────

(
    df_transactions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_pos_sales_transactions")
)

transaction_count = spark.table("bronze.bronze_pos_sales_transactions").count()
print(f"bronze_pos_sales_transactions 保存完了: {transaction_count:,} 件")


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== Bronze レイヤー 保存完了サマリー ===")
print("=" * 50)
print(f"  bronze_store_master             : {store_count:>6,} 件")
print(f"  bronze_product_master           : {product_count:>6,} 件")
print(f"  bronze_customer_master          : {customer_count:>6,} 件")
print(f"  bronze_pos_sales_transactions   : {transaction_count:>6,} 件")
print("=" * 50)


# ──────────────────────────────────────────────
# 6. 保存したテーブルの先頭5件を確認
# ──────────────────────────────────────────────

print("\n=== bronze_store_master 先頭5件 ===")
spark.table("bronze.bronze_store_master").show(5, truncate=False)

print("\n=== bronze_product_master 先頭5件 ===")
spark.table("bronze.bronze_product_master").show(5, truncate=False)

print("\n=== bronze_customer_master 先頭5件 ===")
spark.table("bronze.bronze_customer_master").show(5, truncate=False)

print("\n=== bronze_pos_sales_transactions 先頭5件 ===")
spark.table("bronze.bronze_pos_sales_transactions").show(5, truncate=False)
