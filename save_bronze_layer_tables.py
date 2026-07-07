"""
小売メダリオンアーキテクチャ Bronzeレイヤー保存スクリプト
（Databricks Free Edition Notebook 実行想定）

前提：generate_retail_medallion_sample_data.py を同セッションで実行済みで、
      sampleスキーマに以下4表（データソース由来のサンプルデータ）が
      保存されていること
        - sample.store_master
        - sample.product_master
        - sample.member_master
        - sample.pos_transactions

本スクリプトは sample スキーマの4表を「一切加工せず（列の変更・型変換・
フィルタ・重複排除などを行わず）」そのまま bronze スキーマにコピーする。
Bronzeレイヤーは「生データをそのまま保持する」層であるため、
品質課題（マスター不整合・重複・異常値・欠損・表記揺れ）もそのまま残す。
"""

# ──────────────────────────────────────────────
# 1. bronzeスキーマの作成（存在しない場合のみ）
# ──────────────────────────────────────────────

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
print("スキーマ 'bronze' を確認/作成しました")


# ──────────────────────────────────────────────
# 2. sampleスキーマの4表を読み込み、そのままbronzeスキーマへ保存
#    ※ select や filter、キャストなどの加工は一切行わない
# ──────────────────────────────────────────────

BRONZE_TABLES = [
    "store_master",
    "product_master",
    "member_master",
    "pos_transactions",
]

for table_name in BRONZE_TABLES:
    df_source = spark.table(f"sample.{table_name}")   # 加工せずそのまま読み込み
    (
        df_source.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"bronze.{table_name}")           # 加工せずそのまま保存
    )
    print(f"bronze.{table_name} を保存しました")


# ──────────────────────────────────────────────
# 3. 保存件数の確認（source側とbronze側で件数が一致することを確認）
# ──────────────────────────────────────────────

print("\n" + "=" * 50)
print("=== Bronzeレイヤー 保存結果（件数照合） ===")
print("=" * 50)

for table_name in BRONZE_TABLES:
    source_count = spark.table(f"sample.{table_name}").count()
    bronze_count = spark.table(f"bronze.{table_name}").count()
    match_flag = "OK" if source_count == bronze_count else "NG（件数不一致）"
    print(f"  bronze.{table_name:<20}: sample={source_count:>4,} 件 / bronze={bronze_count:>4,} 件 ... {match_flag}")

print("\n=== Bronzeレイヤー保存完了 ===")
