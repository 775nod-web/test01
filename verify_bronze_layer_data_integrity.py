"""
小売メダリオンアーキテクチャ Bronzeレイヤー データ整合性検証スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：save_bronze_layer_tables.py を同セッションで実行済みで、
      bronzeスキーマに以下4表が保存されていること
        - bronze.store_master
        - bronze.product_master
        - bronze.member_master
        - bronze.pos_transactions

本スクリプトは「sampleスキーマの生データ」と「bronzeスキーマに保存した
データ」を突き合わせ、取り込みメタデータ列（例：_ingested_at 等、
列名が "_" で始まる列）以外のデータが一切変更されずに
Bronzeレイヤーへ保存できているかを検証する。

検証観点：
  (a) 件数が一致するか
  (b) 業務列（メタデータ列以外）のスキーマ（列名・型）が一致するか
  (c) 業務列のデータ内容が1件も欠落・変化・追加なく一致するか
      （sample→bronze、bronze→sampleの双方向差分が0件であること）
"""

BRONZE_TABLES = [
    "store_master",
    "product_master",
    "member_master",
    "pos_transactions",
]

# 取り込みメタデータ列の判定ルール（列名が "_" で始まる列をメタデータ列とみなす）
def is_metadata_column(col_name: str) -> bool:
    return col_name.startswith("_")


print("=" * 70)
print("=== Bronzeレイヤー データ整合性検証 ===")
print("=" * 70)

all_passed = True

for table_name in BRONZE_TABLES:
    df_source = spark.table(f"sample.{table_name}")
    df_bronze = spark.table(f"bronze.{table_name}")

    # メタデータ列を除いた「業務列」のみを比較対象とする
    metadata_cols = [c for c in df_bronze.columns if is_metadata_column(c)]
    business_cols = [c for c in df_source.columns if not is_metadata_column(c)]

    df_source_business = df_source.select(*business_cols)
    df_bronze_business = df_bronze.select(*business_cols)

    print(f"\n--- {table_name} ---")
    if metadata_cols:
        print(f"  検証対象外（取り込みメタデータ列）: {metadata_cols}")
    else:
        print("  検証対象外（取り込みメタデータ列）: なし")

    # (a) 件数一致チェック
    source_count = df_source_business.count()
    bronze_count = df_bronze_business.count()
    count_ok = source_count == bronze_count
    print(f"  (a) 件数比較        : sample={source_count} 件 / bronze={bronze_count} 件 "
          f"... {'OK' if count_ok else 'NG'}")

    # (b) スキーマ（列名・型）一致チェック
    schema_ok = df_source_business.schema == df_bronze_business.schema
    print(f"  (b) スキーマ一致     : {'OK' if schema_ok else 'NG'}")
    if not schema_ok:
        print(f"      sample側: {df_source_business.dtypes}")
        print(f"      bronze側: {df_bronze_business.dtypes}")

    # (c) データ内容一致チェック（双方向差分が0件であること）
    only_in_source = df_source_business.exceptAll(df_bronze_business)
    only_in_bronze = df_bronze_business.exceptAll(df_source_business)
    only_in_source_count = only_in_source.count()
    only_in_bronze_count = only_in_bronze.count()
    data_ok = (only_in_source_count == 0) and (only_in_bronze_count == 0)
    print(f"  (c) データ内容一致   : sample側のみに存在={only_in_source_count} 件 / "
          f"bronze側のみに存在={only_in_bronze_count} 件 ... {'OK' if data_ok else 'NG'}")

    if not data_ok:
        print("      差分レコード（sample側のみに存在）:")
        only_in_source.show(10, truncate=False)
        print("      差分レコード（bronze側のみに存在）:")
        only_in_bronze.show(10, truncate=False)

    table_passed = count_ok and schema_ok and data_ok
    all_passed = all_passed and table_passed
    print(f"  => {table_name} の検証結果: {'PASS（変更なく保存されている）' if table_passed else 'FAIL（差分あり）'}")


print("\n" + "=" * 70)
print(f"=== 総合結果: {'全4表 PASS（生データはBronzeレイヤーに変更なく保存されている）' if all_passed else '一部の表でFAILを検出'} ===")
print("=" * 70)
