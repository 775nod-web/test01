# 🚗 自動車業界向け グローバル・サプライチェーン可視化とデータ共有 デモ

Databricks（Unity Catalog + Delta UniForm + Foundation Model API）を用いた、自動車業界向けの
グローバル・サプライチェーン可視化 / データ共有デモアプリケーションです。
Streamlit で構築されており、Databricks Apps 上での実行を想定しています。

## デモのストーリー

自動車メーカー（OEM）のサプライチェーン管理部門は、部品メーカー（Tier1/Tier2）、物流拠点、港湾
（スエズ運河・パナマ運河・マラッカ海峡などのチョークポイントを含む）、完成車組立工場にまたがる
複雑なグローバル・サプライチェーンを管理しています。

地政学リスク（スエズ運河の座礁事故、台湾有事など）や自然災害（地震、渇水による運河の通航制限など）が
発生した際、**「どの車種の生産に影響が出るのか」「代替サプライヤーはどこか」** を即座に把握することが
求められます。

本デモは、Unity Catalog 上に格納したサプライチェーンデータ（UniForm 有効化により Apache Iceberg
クライアントからも読み取り可能）と、Databricks FMAPI による AI チャットを組み合わせ、この意思決定を
支援するアプリケーションを再現したものです。

1. **📊 ダッシュボード** で世界地図・Sankey図・排出量グラフによりサプライチェーン全体を俯瞰
2. **🚨 リスクシナリオ分析** でシナリオ（スエズ運河停滞・台湾地震 等）を選択し、影響範囲と代替候補を特定
3. **💬 AIチャット** で自由形式の質問に対し、実データを踏まえた分析・提案を取得（RAG的挙動のシミュレーション）
4. **🗂️ データ管理** でサプライヤー・在庫データを追加・更新・削除（Delta テーブルへ即時反映）


## ディレクトリ構成

```
automotive_supply_chain_demo/
├── README.md                  本ファイル
├── requirements.txt            依存ライブラリ
├── data_setup.py                Databricksノートブック用：サンプルデータ生成 & UniForm有効化Deltaテーブル作成
├── app.py                       Streamlitメインアプリケーション
├── .streamlit/
│   └── config.toml              Material Designライクなテーマ設定
└── src/
    ├── config.py                 カタログ/スキーマ名・モデル一覧・カラーパレット等の設定
    ├── sample_data.py             自動車サプライチェーンのサンプルデータ生成ロジック（Pandas）
    ├── db.py                      データアクセス層（Databricks SQL Warehouse / ローカルSQLiteフォールバック）
    ├── llm.py                     Databricks FMAPI 連携 + 簡易RAG（キーワード検索によるコンテキスト取得）
    ├── chat_store.py              チャットスレッド管理（Claude UI風のサイドバー履歴）
    ├── risk_scenarios.py          地政学リスク・自然災害シナリオの定義と影響分析ロジック
    └── visualizations.py          Plotlyによる地図・Sankey・棒グラフ等の可視化コンポーネント
```


## 1. 実行環境とデータ基盤

- **ワークスペース**: `E2-Demo-Field-Eng`（Unity Catalog 有効なワークスペースを前提）
- **ストレージ**: Unity Catalog 管理の Delta テーブル
- **UniForm**: 全テーブルで `delta.universalFormat.enabledFormats = 'iceberg'` を有効化し、
  Apache Iceberg クライアントからも読み取り可能にしています（詳細は後述）
- **サンプルデータ**: `src/sample_data.py` で自動車サプライチェーン（Tier1/Tier2部品メーカー、
  港湾・チョークポイント、完成車組立工場、車種、物流ルート、在庫）を Pandas で生成

生成される主なテーブル（`{catalog}.{schema}.` 配下）:

| テーブル名 | 内容 |
|---|---|
| `suppliers` | Tier1/Tier2 部品サプライヤー拠点（緯度経度・リスクスコア含む） |
| `ports` | 港湾・チョークポイント（スエズ運河、パナマ運河、マラッカ海峡など） |
| `assembly_plants` | 完成車組立工場 |
| `vehicle_models` | 車種マスター |
| `logistics_routes` | サプライヤー→組立工場の物流ルート（輸送モード、Scope3 CO2排出量含む） |
| `vehicle_component_map` | 車種 ↔ 部品カテゴリ ↔ サプライヤーのマッピング |
| `inventory` | 在庫データ（アプリ上の CRUD デモ対象） |


## 2. Databricks 上でのセットアップ手順

### 2.1 データセットアップ（`data_setup.py`）

1. Databricks ワークスペース（`E2-Demo-Field-Eng` 相当、Unity Catalog 有効）にログインします。
2. Repos またはワークスペースファイルとして、この `automotive_supply_chain_demo/` ディレクトリを
   インポートします（Git連携でも、ZIPアップロードでも可）。
3. `data_setup.py` をノートブックとして開き、Unity Catalog 対応クラスター
   （DBR 14.3 LTS 以降推奨、Shared または Single User アクセスモード）にアタッチします。
4. ノートブックウィジェットでカタログ名・スキーマ名を指定（デフォルト:
   `automotive_scm_demo` / `supply_chain`）し、全セルを実行します。
5. 実行が完了すると、7つの Delta テーブルが UniForm 有効化された状態で作成されます。

```python
# data_setup.py の主要処理（抜粋）
UNIFORM_TBLPROPERTIES = (
    "delta.enableIcebergCompatV2 = 'true', "
    "delta.universalFormat.enabledFormats = 'iceberg', "
    "delta.columnMapping.mode = 'name'"
)

(
    sdf.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .option("delta.columnMapping.mode", "name")
    .option("delta.enableIcebergCompatV2", "true")
    .option("delta.universalFormat.enabledFormats", "iceberg")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.{table_name}")
)
spark.sql(f"ALTER TABLE {CATALOG}.{SCHEMA}.{table_name} SET TBLPROPERTIES ({UNIFORM_TBLPROPERTIES})")
```

### 2.2 アプリケーションの実行（`app.py`）

**Databricks Apps を使う場合（推奨）:**

1. Databricks ワークスペースの「Apps」から新規アプリを作成し、この `automotive_supply_chain_demo/`
   ディレクトリをソースとして指定します。
2. アプリの環境変数に以下を設定します（Databricks Apps では `DATABRICKS_HOST` 等はランタイムが
   自動的に注入する場合があります。SQL Warehouse への接続情報は明示的に設定してください）。

   | 環境変数 | 説明 |
   |---|---|
   | `DATABRICKS_HOST` | ワークスペースのホスト名（例: `xxx.cloud.databricks.com`） |
   | `DATABRICKS_TOKEN` | Personal Access Token または Apps用サービスプリンシパルトークン |
   | `DATABRICKS_HTTP_PATH` | 使用する SQL Warehouse の HTTP Path |
   | `SCM_CATALOG` | `data_setup.py` で指定したカタログ名（デフォルト: `automotive_scm_demo`） |
   | `SCM_SCHEMA` | `data_setup.py` で指定したスキーマ名（デフォルト: `supply_chain`） |

3. `requirements.txt` が自動的にインストールされます。エントリポイントは `app.py` です。
4. FMAPI の Serving Endpoints（`databricks-meta-llama-3-1-70b-instruct` 等）へのアクセス権限が
   アプリのサービスプリンシパルに付与されていることを確認してください。

**ローカル環境で動作確認する場合:**

```bash
cd automotive_supply_chain_demo
pip install -r requirements.txt
streamlit run app.py
```

`DATABRICKS_HOST` / `DATABRICKS_TOKEN` / `DATABRICKS_HTTP_PATH` が未設定の場合、アプリは自動的に
**ローカルデモモード**（SQLite バックエンド、`data_setup.py` と同じサンプルデータを自動生成）で
起動し、Databricks 環境なしでも UI・操作感を確認できます。サイドバーのバッジで
現在のモード（Databricks接続中 / ローカルデモモード）を確認できます。


## 3. UniForm / Iceberg 有効化の確認方法

Databricks SQL エディタまたはノートブックで以下を実行します。

```sql
-- テーブルプロパティで UniForm が有効化されていることを確認
SHOW TBLPROPERTIES automotive_scm_demo.supply_chain.suppliers;
-- delta.universalFormat.enabledFormats = iceberg が含まれていることを確認

-- Iceberg メタデータの出力先を確認
DESCRIBE DETAIL automotive_scm_demo.supply_chain.suppliers;
```

Apache Iceberg クライアント（Spark の Iceberg カタログ、PyIceberg、Trino など）から読み取る場合は、
Unity Catalog の Iceberg REST Catalog エンドポイント（`https://<workspace-host>/api/2.1/unity-catalog/iceberg`）
を使用して接続できます。例えば PyIceberg では以下のように接続します。

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "uc",
    **{
        "uri": "https://<workspace-host>/api/2.1/unity-catalog/iceberg",
        "token": "<PAT>",
        "warehouse": "automotive_scm_demo",
    },
)
table = catalog.load_table("supply_chain.suppliers")
print(table.scan().to_pandas())
```


## 4. アプリケーション機能

### AIチャット（💬）
- サイドバーで Databricks FMAPI のモデルエンドポイントを選択（`databricks-meta-llama-3-1-70b-instruct`、
  `databricks-mixtral-8x7b-instruct` 等）
- Claude の UI を参考に、サイドバーにチャット履歴（スレッド）を保持・切り替え・削除可能
- 質問文からキーワード（拠点名・部品カテゴリ・国名等）を抽出し、Unity Catalog 上のテーブルから
  関連データを検索してコンテキストとして LLM に渡す、RAG的挙動をシミュレーション
  （`src/llm.py` の `retrieve_context()`）。回答の下に「参照データ」として取得内容を表示し、
  根拠を透明化しています。

### ダッシュボード（📊）
- 世界地図上にサプライヤー（Tier1/Tier2）・港湾/チョークポイント・完成車組立工場・物流ルートを表示
- 地域別リスクスコア、部品カテゴリ別 Scope3 CO2排出量、サプライヤー階層→部品→OEM の Sankey図

### リスクシナリオ分析（🚨）
- スエズ運河停滞・台湾地震・日本地震・パナマ運河渇水・マラッカ海峡混雑の5シナリオを用意
- 選択したシナリオに応じて影響サプライヤー・物流ルート（地図上で赤くハイライト）・影響車種・
  影響在庫・代替サプライヤー候補を自動抽出
- 「AIに詳細な代替案・提言を聞く」ボタンでチャットに引き継ぎ、詳細な提案を取得

### データ管理（🗂️）
- 在庫（`inventory`）・サプライヤー（`suppliers`）テーブルに対する挿入・更新・削除
- Delta テーブル（本番）/ SQLite（ローカルデモ）のいずれに対しても同じ操作感で動作


## 5. デザイン

Google の Material Design を参考に、白背景 + アクセントカラー（青 `#4285F4` / 赤 `#EA4335` /
黄 `#FBBC05` / 緑 `#34A853`）で統一しています（`src/config.py` のカラーパレット定義、
`.streamlit/config.toml` のテーマ設定）。


## 6. 補足事項

- 地図の可視化には Plotly の `Scattergeo` を使用していますが、外部CDN（`cdn.plot.ly`）から
  地形データ（topojson）を取得する標準機能は利用していません。社内ネットワーク等でインターネット
  アクセスが制限された Databricks 環境でも確実に描画できるよう、簡略化した大陸の輪郭を
  アプリ内に直接埋め込んで自前描画しています（`src/visualizations.py`）。
- 本デモの RAG的挙動は、Databricks Vector Search 等によるベクトル検索の代替として、
  キーワードマッチによる簡易的なテーブル検索を実装したものです。本番用途では
  Databricks Vector Search + Delta テーブルの CDC 連携などへの拡張を推奨します。
- サンプルデータはすべて架空のものです（実在の企業名を示唆する `-style` 命名としています）。
