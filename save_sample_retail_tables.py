# Databricks ノートブック用
# generate_retail_sample_data.py で生成した DataFrame
# （df_pos_transactions / df_product_master / df_store_master / df_member_master）を
# サンプルデータ用スキーマの Delta テーブルとして保存する
#
# 前提：generate_retail_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

spark.sql("CREATE DATABASE IF NOT EXISTS sample")
spark.sql("USE sample")

print("データベース 'sample' を選択しました")


# ──────────────────────────────────────────────
# 1. POSトランザクション → sample_pos_transactions
# ──────────────────────────────────────────────

(
    df_pos_transactions
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.sample_pos_transactions")
)
pos_count = spark.table("sample.sample_pos_transactions").count()
print(f"sample_pos_transactions 保存完了: {pos_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → sample_product_master
# ──────────────────────────────────────────────

(
    df_product_master
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.sample_product_master")
)
product_count = spark.table("sample.sample_product_master").count()
print(f"sample_product_master 保存完了: {product_count:,} 件")


# ──────────────────────────────────────────────
# 3. 店舗マスター → sample_store_master
# ──────────────────────────────────────────────

(
    df_store_master
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.sample_store_master")
)
store_count = spark.table("sample.sample_store_master").count()
print(f"sample_store_master 保存完了: {store_count:,} 件")


# ──────────────────────────────────────────────
# 4. 会員マスター → sample_member_master
# ──────────────────────────────────────────────

(
    df_member_master
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("sample.sample_member_master")
)
member_count = spark.table("sample.sample_member_master").count()
print(f"sample_member_master 保存完了: {member_count:,} 件")


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== sample スキーマ 保存完了サマリー ===")
print("=" * 40)
print(f"  sample_pos_transactions : {pos_count:>6,} 件")
print(f"  sample_product_master   : {product_count:>6,} 件")
print(f"  sample_store_master     : {store_count:>6,} 件")
print(f"  sample_member_master    : {member_count:>6,} 件")
print("=" * 40)
