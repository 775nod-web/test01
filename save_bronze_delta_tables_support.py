# Databricks ノートブック用
# 生成済み DataFrame（df_customer_master / df_contract_data / df_support_tickets）を
# Bronze レイヤーの Delta テーブルとして Hive メタストアに保存する
#
# 前提：generate_support_ticket_sample_data.py を同セッションで実行済みであること
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
# 1. 顧客マスター → bronze_customer_master
# ──────────────────────────────────────────────

(
    df_customer_master                              # 生成済み顧客マスター DataFrame（15件）
    .write
    .format("delta")                                 # Delta Lake 形式で保存
    .mode("overwrite")                                # 既存テーブルを上書き（冪等実行を保証）
    .option("overwriteSchema", "true")               # スキーマ変更も上書き許可
    .saveAsTable("bronze.bronze_customer_master")     # Hive メタストアにテーブルとして登録
)

customer_master_count = spark.table("bronze.bronze_customer_master").count()
print(f"bronze_customer_master 保存完了: {customer_master_count:,} 件")


# ──────────────────────────────────────────────
# 2. 契約データ → bronze_contract_data
# ──────────────────────────────────────────────

(
    df_contract_data                              # 生成済み契約データ DataFrame（15件）
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_contract_data")
)

contract_data_count = spark.table("bronze.bronze_contract_data").count()
print(f"bronze_contract_data 保存完了: {contract_data_count:,} 件")


# ──────────────────────────────────────────────
# 3. サポートチケット → bronze_support_tickets
# ──────────────────────────────────────────────

(
    df_support_tickets                              # 生成済みサポートチケット DataFrame（53件、品質課題27件を含む）
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("bronze.bronze_support_tickets")
)

support_tickets_count = spark.table("bronze.bronze_support_tickets").count()
print(f"bronze_support_tickets 保存完了: {support_tickets_count:,} 件")


# ──────────────────────────────────────────────
# 4. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print("=== Bronze レイヤー 保存完了サマリー ===")
print("=" * 40)
print(f"  bronze_customer_master : {customer_master_count:>6,} 件")
print(f"  bronze_contract_data   : {contract_data_count:>6,} 件")
print(f"  bronze_support_tickets : {support_tickets_count:>6,} 件")
print("=" * 40)


# ──────────────────────────────────────────────
# 5. Delta テーブルの履歴確認（任意）
# ──────────────────────────────────────────────

print("\n=== bronze_support_tickets の Delta 履歴 ===")
spark.sql("DESCRIBE HISTORY bronze.bronze_support_tickets").select(
    "version", "timestamp", "operation", "operationParameters"
).show(truncate=False)


# ──────────────────────────────────────────────
# 6. 保存したテーブルの先頭5件を確認
# ──────────────────────────────────────────────

print("\n=== bronze_customer_master 先頭5件 ===")
spark.table("bronze.bronze_customer_master").show(5, truncate=False)

print("\n=== bronze_contract_data 先頭5件 ===")
spark.table("bronze.bronze_contract_data").show(5, truncate=False)

print("\n=== bronze_support_tickets 先頭5件 ===")
spark.table("bronze.bronze_support_tickets").show(5, truncate=False)
