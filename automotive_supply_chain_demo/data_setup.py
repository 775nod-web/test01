# Databricks ノートブック用スクリプト
#
# 自動車サプライチェーンのサンプルデータを生成し、Unity Catalog 上に
# Delta テーブル（UniForm を有効化 = Apache Iceberg クライアントからも読み取り可能）として保存する。
#
# 前提:
#   - ワークスペース: E2-Demo-Field-Eng（Unity Catalog 有効）
#   - 実行方法: Databricks ノートブックとしてこのファイルをインポートし、
#     Unity Catalog 対応クラスター（Shared / Single User, DBR 14.3 LTS 以降推奨）にアタッチして実行する。
#     もしくは Databricks Job のタスクとして実行する。
#
# 生成するテーブル（すべて {catalog}.{schema} 配下）:
#   - suppliers               : Tier1/Tier2 部品サプライヤー拠点
#   - ports                   : 港湾・チョークポイント（スエズ運河等）
#   - assembly_plants         : 完成車組立工場
#   - vehicle_models          : 車種マスター
#   - logistics_routes        : サプライヤー → 組立工場の物流ルート（Scope3 CO2 排出量含む）
#   - vehicle_component_map   : 車種 ↔ 部品カテゴリ ↔ サプライヤーのマッピング
#   - inventory               : 在庫データ（アプリ上の CRUD デモ対象）

# ──────────────────────────────────────────────
# 0. 設定・準備
# ──────────────────────────────────────────────

import sys
import os

# このノートブック/スクリプトから src パッケージを import できるようにする
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src import sample_data  # noqa: E402

# Databricks ノートブック上では widgets が使える場合、カタログ／スキーマ名を
# パラメータ化できるようにしておく（ジョブ実行時に上書き可能）
try:
    dbutils.widgets.text("catalog", "automotive_scm_demo", "Unity Catalog カタログ名")
    dbutils.widgets.text("schema", "supply_chain", "スキーマ名")
    CATALOG = dbutils.widgets.get("catalog")
    SCHEMA = dbutils.widgets.get("schema")
except NameError:
    # dbutils が無い環境（ローカル検証等）では環境変数 or デフォルト値を使用
    CATALOG = os.environ.get("SCM_CATALOG", "automotive_scm_demo")
    SCHEMA = os.environ.get("SCM_SCHEMA", "supply_chain")

print(f"対象カタログ: {CATALOG}")
print(f"対象スキーマ: {SCHEMA}")

# UniForm（Iceberg 互換）を有効化する Delta テーブルプロパティ
# - delta.universalFormat.enabledFormats = 'iceberg' : Iceberg クライアントからの読み取りを可能にする
# - delta.enableIcebergCompatV2 = 'true'             : UniForm 利用に必要な IcebergCompatV2 を有効化
# - delta.columnMapping.mode = 'name'                : IcebergCompatV2 の前提条件（列マッピング）
UNIFORM_TBLPROPERTIES = (
    "delta.enableIcebergCompatV2 = 'true', "
    "delta.universalFormat.enabledFormats = 'iceberg', "
    "delta.columnMapping.mode = 'name'"
)


# ──────────────────────────────────────────────
# 1. カタログ／スキーマの作成（冪等）
# ──────────────────────────────────────────────

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"USE SCHEMA {SCHEMA}")

print(f"カタログ '{CATALOG}' / スキーマ '{SCHEMA}' を準備しました")


# ──────────────────────────────────────────────
# 2. サンプルデータ生成（Pandas → Spark DataFrame）
# ──────────────────────────────────────────────

pandas_tables = sample_data.generate_all()

spark_tables = {}
for name, pdf in pandas_tables.items():
    # Databricks ノートブック上では spark はクラスターから自動注入されるため
    # SparkSession.builder は呼ばない
    sdf = spark.createDataFrame(pdf)
    spark_tables[name] = sdf
    print(f"生成: {name} ({sdf.count()} 件)")


# ──────────────────────────────────────────────
# 3. Delta テーブルとして保存（UniForm/Iceberg 有効化）
# ──────────────────────────────────────────────

def save_as_uniform_table(sdf, table_name: str):
    """DataFrame を UniForm 有効化済みの Delta テーブルとして保存する"""
    full_name = f"{CATALOG}.{SCHEMA}.{table_name}"
    (
        sdf.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.columnMapping.mode", "name")
        .option("delta.enableIcebergCompatV2", "true")
        .option("delta.universalFormat.enabledFormats", "iceberg")
        .saveAsTable(full_name)
    )
    # saveAsTable のオプションに加えて、確実に反映させるため ALTER TABLE でも明示設定する
    spark.sql(f"""
        ALTER TABLE {full_name}
        SET TBLPROPERTIES ({UNIFORM_TBLPROPERTIES})
    """)
    print(f"保存完了（UniForm有効）: {full_name}")


for table_name, sdf in spark_tables.items():
    save_as_uniform_table(sdf, table_name)


# ──────────────────────────────────────────────
# 4. UniForm / Iceberg 有効化の確認
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== UniForm（Iceberg互換）設定の確認 ===")
print("=" * 60)

for table_name in spark_tables.keys():
    full_name = f"{CATALOG}.{SCHEMA}.{table_name}"
    props = spark.sql(f"SHOW TBLPROPERTIES {full_name}").toPandas()
    uniform_props = props[props["key"].str.contains("universalFormat|IcebergCompat", regex=True)]
    print(f"\n--- {full_name} ---")
    print(uniform_props.to_string(index=False))

print("\nIceberg メタデータの場所は DESCRIBE DETAIL で確認できます。例:")
print(f"  DESCRIBE DETAIL {CATALOG}.{SCHEMA}.suppliers")
print("\nIceberg REST Catalog 経由でのアクセス方法は README.md を参照してください。")


# ──────────────────────────────────────────────
# 5. 保存結果サマリー
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("=== データセットアップ 完了サマリー ===")
print("=" * 60)
for table_name, sdf in spark_tables.items():
    print(f"  {CATALOG}.{SCHEMA}.{table_name:<24}: {sdf.count():>6,} 件")
print("=" * 60)
print("\nアプリケーション（app.py）から参照する場合は、以下の環境変数を設定してください:")
print("  SCM_CATALOG, SCM_SCHEMA, DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH")
