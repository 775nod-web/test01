# Databricks ノートブック用
# Bronzeレイヤーに保存したデータについて、取り込みメタデータ列を除いた
# 生データ部分がsampleスキーマ（取り込み元）の内容から一切変更されていないことを検証する
#
# 前提：sample.sample_* と bronze.bronze_* の両方が存在すること
#       （generate/save_sample_retail_tables.py と save_bronze_layer_tables.py を実行済みであること）

CATALOG = spark.catalog.currentCatalog()
SAMPLE_SCHEMA = f"{CATALOG}.sample"
BRONZE_SCHEMA = f"{CATALOG}.bronze"

# Bronze取り込み時に付与した取り込みメタデータ列（検証対象から除外する）
METADATA_COLUMNS = ["_bronze_ingested_at", "_bronze_source_system", "_bronze_batch_id"]

TABLE_PAIRS = [
    ("sample_pos_transactions", "bronze_pos_transactions"),
    ("sample_product_master",   "bronze_product_master"),
    ("sample_store_master",     "bronze_store_master"),
    ("sample_member_master",    "bronze_member_master"),
]

print("=== Bronzeレイヤー 生データ無変更検証 ===\n")

all_passed = True
for sample_table, bronze_table in TABLE_PAIRS:
    df_sample = spark.table(f"{SAMPLE_SCHEMA}.{sample_table}")
    df_bronze_raw = spark.table(f"{BRONZE_SCHEMA}.{bronze_table}")

    # 取り込みメタデータ列を除いた「生データ列」のみをBronze側から取り出す
    original_columns = df_sample.columns
    df_bronze_original_cols = df_bronze_raw.select(*original_columns)

    sample_count = df_sample.count()
    bronze_count = df_bronze_original_cols.count()
    count_match = sample_count == bronze_count

    # 行単位の完全一致比較（重複行も区別するため distinct を取らない exceptAll を使用）
    only_in_sample = df_sample.exceptAll(df_bronze_original_cols)
    only_in_bronze = df_bronze_original_cols.exceptAll(df_sample)
    diff_count = only_in_sample.count() + only_in_bronze.count()

    passed = count_match and diff_count == 0
    all_passed = all_passed and passed

    status = "OK" if passed else "NG"
    print(f"[{status}] {bronze_table}")
    print(f"      件数一致          : sample={sample_count:,}件 / bronze={bronze_count:,}件 → {'一致' if count_match else '不一致'}")
    print(f"      行内容の差分件数  : {diff_count:,} 件")

    if not passed:
        print("      -- sampleのみに存在する行（先頭5件） --")
        only_in_sample.show(5, truncate=False)
        print("      -- bronzeのみに存在する行（先頭5件） --")
        only_in_bronze.show(5, truncate=False)

    # 取り込みメタデータ列が想定通り付与されているかも確認する
    metadata_present = all(col in df_bronze_raw.columns for col in METADATA_COLUMNS)
    print(f"      取り込みメタデータ列の付与: {'OK' if metadata_present else 'NG'} {METADATA_COLUMNS}")
    print()

print("=" * 50)
if all_passed:
    print("=== 総合判定: OK（全表でBronzeの生データはsampleから変更されていません） ===")
else:
    print("=== 総合判定: NG（差分のある表があります。上記の差分行を確認してください） ===")
print("=" * 50)
