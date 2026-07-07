# Databricks ノートブック用
# generate_retail_sample_data.py で生成した DataFrame
# （df_pos_transactions / df_product_master / df_store_master / df_member_master）を
# サンプルデータ用スキーマの Delta テーブルとして保存する
#
# 前提：generate_retail_sample_data.py を同セッションで実行済みであること
# 動作確認環境：Databricks Free Edition
#
# Databricks Free EditionはUnity Catalogが有効なため、テーブルは
# 本来 catalog.schema.table の3階層で管理される。
# "sample.sample_pos_transactions" のようにカタログ名を省略すると、
# 実行時点の current_catalog() 配下に解決されるため、
# 別セッション/別ノートブックで current_catalog() が異なると
# 保存したテーブルが見つからなくなる（TABLE_OR_VIEW_NOT_FOUND）。
# これを避けるため、カタログ名を明示的に取得してすべて3階層で保存する。

# ──────────────────────────────────────────────
# 0. 保存先カタログ・スキーマの決定と作成
#    存在しない場合のみ作成する（冪等性を確保）
# ──────────────────────────────────────────────

CATALOG = spark.catalog.currentCatalog()
SCHEMA_NAME = "sample"
FULL_SCHEMA = f"{CATALOG}.{SCHEMA_NAME}"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FULL_SCHEMA}")
spark.sql(f"USE {FULL_SCHEMA}")

print(f"カタログ '{CATALOG}' / スキーマ '{SCHEMA_NAME}' を使用します（{FULL_SCHEMA}）")


# ──────────────────────────────────────────────
# 1〜4. 各DataFrameをDeltaテーブルとして保存
#    保存後すぐに件数を確認することで、保存先の取り違えを早期に検知する
# ──────────────────────────────────────────────

def save_delta_table(df, table_name: str) -> int:
    """DataFrameを {CATALOG}.{SCHEMA_NAME}.{table_name} にDelta形式で保存し、保存件数を返す"""
    full_name = f"{FULL_SCHEMA}.{table_name}"
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_name)
    )
    count = spark.table(full_name).count()
    print(f"{full_name} 保存完了: {count:,} 件")
    return count


pos_count = save_delta_table(df_pos_transactions, "sample_pos_transactions")
product_count = save_delta_table(df_product_master, "sample_product_master")
store_count = save_delta_table(df_store_master, "sample_store_master")
member_count = save_delta_table(df_member_master, "sample_member_master")


# ──────────────────────────────────────────────
# 5. 保存結果サマリーの表示
# ──────────────────────────────────────────────

print("\n" + "=" * 40)
print(f"=== {FULL_SCHEMA} 保存完了サマリー ===")
print("=" * 40)
print(f"  sample_pos_transactions : {pos_count:>6,} 件")
print(f"  sample_product_master   : {product_count:>6,} 件")
print(f"  sample_store_master     : {store_count:>6,} 件")
print(f"  sample_member_master    : {member_count:>6,} 件")
print("=" * 40)

# 次のセル（display_retail_data_quality_summary.py）でも
# 同じ current_catalog() を利用するため、このセッション内であれば
# spark.table(f"{FULL_SCHEMA}.sample_pos_transactions") 等でそのまま参照できる
