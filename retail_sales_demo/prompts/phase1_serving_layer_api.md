# Phase 1 プロンプト: Serving Layer バックエンドAPI実装

Phase 0 完了後、以下をそのままコーディングエージェントに投入してください。

---

あなたはDatabricksワークスペースに接続されたコーディングエージェントです。`retail_sales_demo/CLAUDE.md` の制約とGoldスキーマ定義に従い、Serving layerのバックエンドAPIを実装してください。Phase 0で確認したカタログ/スキーマ名・Warehouse情報を前提とします。

## 目的

Gold layerの4テーブルを、Databricks Apps上で動くReactフロントエンドから利用できる形でREST API化する。クエリエンジンはWarehouse ID `50153ad923fecd73`（環境変数`DATABRICKS_WAREHOUSE_ID`経由）を使用する。

## 実装するエンドポイント

| メソッド/パス | 説明 | 参照テーブル |
|---|---|---|
| `GET /api/kpi-summary` | net sales, gross sales(暫定), transaction count, units sold, average basket size を期間・店舗条件で集計 | `gold_daily_store_sales` |
| `GET /api/daily-store-sales` | 日別×店舗の売上推移（時系列チャート用） | `gold_daily_store_sales` |
| `GET /api/category-sales` | カテゴリ別売上構成 | `gold_category_sales` |
| `GET /api/store-ranking` | 店舗ランキング | `gold_store_ranking` |
| `GET /api/quarantine-report` | マスター未登録取引一覧（issue_typeでフィルタ可） | `gold_unregistered_master_report` |

すべてのエンドポイントは `store_id` によるクエリパラメータフィルタをサポートし、店舗別アクセス制御（Phase 3で実装）と組み合わせられるようにしておくこと。

## gross sales に関する既知のギャップへの対応

`gold_daily_store_sales` と `gold_category_sales` にはdiscount集約列が存在しないため、gross salesを正確に算出できない。`kpi-summary` のレスポンスでは `gross_sales` を `net_sales` と同値で返しつつ、`gross_sales_is_estimated: true` のようなフラグを含め、フロントエンド側で「暫定値」であることを明示できるようにすること。正確な算出には Gold layer への discount 集約列追加が必要である旨をレスポンスまたはコメントで明記する。

## 完了条件

- 上記5エンドポイントが実装され、Warehouse `50153ad923fecd73` に対してクエリを発行し、正しいレスポンスを返すことを確認する。
- 各エンドポイントの入出力仕様（OpenAPI/簡易なMarkdown表のいずれか）をドキュメント化する。
- 実装完了時に、以下の説明をコードと合わせて出力すること:
  - このAPI設計がビジネス目的（早期把握・傾向把握・データ品質フォロー）にどう貢献するか
  - Serverless SQL Warehouseをどのように利用したか、なぜこの構成がFree Editionに適しているか
