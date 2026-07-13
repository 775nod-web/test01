# Databricks ノートブック用
# 生成済み DataFrame（df_orders / df_products / df_users）を
# Bronze レイヤーの Delta テーブルとして Hive メタストアに保存する
#
# 前提：generate_ecommerce_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition（Unity Catalog 不使用・Hive メタストア）

# ──────────────────────────────────────────────
# 0. 保存先データベース（スキーマ）の作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

# Bronze レイヤー用データベースを作成（既存の場合はスキップ）
spark.sql("CREATE DATABASE IF NOT EXISTS bronze")

# 以降のテーブルを bronze データベースに対して操作するよう設定
spark.sql("USE bronze")

print("データベース 'bronze' を選択しました")


# ──────────────────────────────────────────────
# 1. 売上トランザクション → bronze_orders
# ──────────────────────────────────────────────

(
    df_orders                            # 生成済み売上トランザクション DataFrame（1020件）
    .write
    .format("delta")                     # Delta Lake 形式で保存
    .mode("overwrite")                   # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")   # スキーマ変更も上書き許可
    .saveAsTable("bronze.bronze_orders") # Hive メタストアにテーブルとして登録
)

# 保存件数を確認
orders_count = spark.table("bronze.bronze_orders").count()
print(f"bronze_orders 保存完了: {orders_count:,} 件")


# ──────────────────────────────────────────────
# 2. 商品マスター → bronze_products
# ──────────────────────────────────────────────

(
    df_products                             # 生成済み商品マスター DataFrame（20件）
    .write
    .format("delta")                        # Delta Lake 形式で保存
    .mode("overwrite")                      # 既存テーブルを上書き
    .option("overwriteSchema", "true")      # スキーマ変更も上書き許可
    .saveAsTable("bronze.bronze_products")  # Hive メタストアにテーブルとして登録
)

# 保存件数を確認
products_count = spark.table("bronze.bronze_products").count()
print(f"bronze_products 保存完了: {products_count:,} 件")


# ──────────────────────────────────────────────
# 3. ユーザーマスター → bronze_users
# ──────────────────────────────────────────────

(
    df_users                             # 生成済みユーザーマスター DataFrame（100件）
    .write
    .format("delta")                     # Delta Lake 形式で保存
    .mode("overwrite")                   # 既存テーブルを上書き
    .option("overwriteSchema", "true")   # スキーマ変更も上書き許可
    .saveAsTable("bronze.bronze_users")  # Hive メタストアにテーブルとして登録
)

# 保存件数を確認
users_count = spark.table("bronze.bronze_users").count()
print(f"bronze_users 保存完了: {users_count:,} 件")


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Bronze レイヤー 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_orders   : {orders_count:>6,} 件")
print(f"  bronze_products : {products_count:>6,} 件")
print(f"  bronze_users    : {users_count:>6,} 件")
print("=" * 40)


# ──────────────────────────────────────────────
# 5. Delta テーブルの履歴確認（任意）
#    DESCRIBE HISTORY で書き込み操作のログを確認できる
# ──────────────────────────────────────────────

print("\n=== bronze_orders の Delta 履歴 ===")
spark.sql("DESCRIBE HISTORY bronze.bronze_orders").select(
    "version", "timestamp", "operation", "operationParameters"
).show(truncate=False)


# ──────────────────────────────────────────────
# 6. 保存したテーブルの先頭5件を確認
# ──────────────────────────────────────────────

print("\n=== bronze_orders 先頭5件 ===")
spark.table("bronze.bronze_orders").show(5, truncate=False)

print("\n=== bronze_products 先頭5件 ===")
spark.table("bronze.bronze_products").show(5, truncate=False)

print("\n=== bronze_users 先頭5件 ===")
spark.table("bronze.bronze_users").show(5, truncate=False)
