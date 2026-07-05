# Phase 1: Serving Layer バックエンドAPI実装 — 結果報告

実施日: 2026-07-05

## 実装したもの

`app/backend/` 配下に FastAPI ベースの Serving layer API を実装した。

```
app/
  app.yaml                      # Databricks Apps デプロイ設定
  requirements.txt
  backend/
    config.py                  # GOLD_CATALOG/GOLD_SCHEMA/SILVER_SCHEMA/DATABRICKS_WAREHOUSE_ID
    db.py                      # SQL Warehouse接続(databricks-sql-connector)
    schema_assumptions.py       # ★Goldテーブルの列名の前提（下記「未検証の前提」参照）
    queries.py                 # エンドポイントごとの純粋なSQLビルダー（DB接続なしでテスト可能）
    main.py                    # 5エンドポイントの実装
    tests/
      test_queries.py          # SQL/パラメータ組み立てのユニットテスト
      test_api.py              # run_queryをモックしたAPIレベルのテスト
  docs/
    openapi.json                # 生成済みOpenAPIスキーマ
```

## エンドポイント仕様

全エンドポイントは `store_id`（カンマ区切りで複数店舗指定可、例 `S001,S002`）による絞り込みに対応。
Phase 3のアクセス制御は、リクエストの `store_id` とユーザーの許可店舗リストをアプリ層で積集合してから
ここに渡す形で組み合わせられる（クエリビルダー自体の変更は不要）。

### `GET /api/kpi-summary`

参照: `gold_daily_store_sales`

| クエリパラメータ | 型 | 説明 |
|---|---|---|
| `store_id` | string (optional) | カンマ区切り店舗ID |
| `date_from` | date (optional) | 集計開始日（含む） |
| `date_to` | date (optional) | 集計終了日（含む） |

レスポンス:

```json
{
  "net_sales": 1234500.0,
  "gross_sales": 1234500.0,
  "gross_sales_is_estimated": true,
  "gross_sales_note": "gold_daily_store_sales / gold_category_sales には discount 集約列が存在しないため、gross_sales は net_sales と同値の暫定値です。正確な gross sales の算出には Gold layer への discount 集約列の追加が必要です。",
  "transaction_count": 230,
  "units_sold": 512,
  "average_basket_size": 5367.4
}
```

`average_basket_size` は `SUM(net_sales) / SUM(transaction_count)`（重み付き平均）で算出し、
取引件数が0の場合は `null` を返す。

### `GET /api/daily-store-sales`

参照: `gold_daily_store_sales`。日別×店舗の時系列データを配列で返す（時系列チャート用）。
パラメータは `kpi-summary` と同じ。各要素: `sales_date, store_id, store_name, net_sales, transaction_count, units_sold`。

### `GET /api/category-sales`

参照: `gold_category_sales`。指定期間・店舗の範囲でカテゴリ別に集計し、
`net_sales` 降順で返す。各要素: `category_id, category_name, net_sales, units_sold, share_of_net_sales`
（`share_of_net_sales` はレスポンス内の合計に対する構成比、APIサーバ側で計算）。

### `GET /api/store-ranking`

参照: `gold_store_ranking`。`rank` 昇順で返す。各要素: `ranking_date, store_id, store_name, net_sales, rank`。
`store_id` を指定すると、その店舗（群）に絞ったランキング一覧になる。

### `GET /api/quarantine-report`

参照: `gold_unregistered_master_report`。`store_id` に加え `issue_type`（カンマ区切り、例
`UNKNOWN_PRODUCT,UNKNOWN_STORE`）でも絞り込み可能。各要素: `transaction_date, transaction_id, store_id,
product_id, issue_type, net_sales, quantity`。`transaction_date` 降順。

完全なOpenAPIスキーマは `docs/openapi.json` に生成済み（`app.openapi()` の出力）。

## gross sales の暫定対応について

`gold_daily_store_sales` / `gold_category_sales` に discount（値引き）の集約列がないため、
gross sales（値引き前売上）を正確に算出できない。そのため `kpi-summary` は `gross_sales` を
`net_sales` と同値で返しつつ、`gross_sales_is_estimated: true` と `gross_sales_note` で暫定値である
ことを明示している。フロントエンドはこのフラグを見て「暫定値」バッジ等を表示する想定。恒久対応には
Gold layer（`gold_daily_store_sales` / `gold_category_sales` の集計元）に discount 集約列を追加する
必要がある。

## ⚠️ 未検証の前提（重要）

このコーディングエージェントセッションは Phase 0 の時点から一貫して **Databricksワークスペースへの
ネットワーク到達性を持たない**（セッションのエグレスポリシーが `dbc-74bfd917-30ed.cloud.databricks.com`
へのCONNECTを403で拒否）。そのため以下は実施できていない:

1. **実際のGoldテーブルのカラム名確認** — `schema_assumptions.py` に定義した列名（`sales_date`,
   `store_id`, `store_name`, `net_sales`, `transaction_count`, `units_sold`, `category_id`,
   `category_name`, `ranking_date`, `rank`, `transaction_date`, `transaction_id`, `product_id`,
   `issue_type`, `quantity`）は **プロンプトの記述から推測した前提であり、`DESCRIBE TABLE` 等で
   実テーブルに対して確認できていない**。実際の列名と異なる場合、`queries.py` はこの前提を経由して
   SQLを組み立てているため、`schema_assumptions.py` の該当箇所を修正するだけで追従できる設計にしてある。
2. **Warehouse `50153ad923fecd73` に対する実クエリ発行・レスポンス確認** — 完了条件にある
   「Warehouseに対してクエリを発行し、正しいレスポンスを返すことを確認する」は、ネットワーク到達性がない
   ため本セッションでは実施できていない。

代わりに実施した検証:

- `backend/tests/test_queries.py`: 5エンドポイント全てのSQL/パラメータ組み立て（フィルタ条件のWHERE句化、
  IN句のバインドパラメータ化、日付範囲条件）をDB接続なしで検証（12件、全てPASS）。
- `backend/tests/test_api.py`: `run_query` をモックし、FastAPI経由でのリクエスト〜レスポンス組み立て
  （`store_id`/`issue_type` のクエリパラメータ解析、`gross_sales_is_estimated` フラグ、
  `average_basket_size` のゼロ除算処理、`share_of_net_sales` の構成比計算）を検証（5件、全てPASS）。
- `app.openapi()` を実行し、5エンドポイントが例外なくOpenAPIスキーマとして生成されることを確認。

**Databricksワークスペースに到達可能な環境（Databricksノートブック上のエージェントセッション等）で
以下を実行し、本ドキュメントを更新すること:**

```sql
DESCRIBE TABLE workspace.gold.gold_daily_store_sales;
DESCRIBE TABLE workspace.gold.gold_category_sales;
DESCRIBE TABLE workspace.gold.gold_store_ranking;
DESCRIBE TABLE workspace.gold.gold_unregistered_master_report;
```

列名が `schema_assumptions.py` と異なる場合は同ファイルを修正し、その後アプリを実際に起動して
5エンドポイントに対して手動またはスクリプトでリクエストを送り、レスポンスが妥当か確認する
（例: `uvicorn backend.main:app --reload` を起動し `curl localhost:8000/api/kpi-summary`）。

## このAPI設計がビジネス目的にどう貢献するか

- **早期把握（KPI summary / daily-store-sales）**: `kpi-summary` は期間・店舗を絞った単一のサマリーを
  1リクエストで返すため、ダッシュボードのトップに「今どうなっているか」を即座に表示できる。
  `daily-store-sales` は同じフィルタ条件で時系列を返すため、サマリーとチャートが同じ絞り込み条件で
  一貫した数字になり、異常な変動（急落・急伸）を早期に視覚的に検知できる。
- **傾向把握（category-sales / store-ranking）**: `category-sales` はカテゴリ構成比を返すため、
  どのカテゴリが売上を牽引しているか／落ち込んでいるかをフロントエンドで円グラフ・棒グラフとして
  即座に表現できる。`store-ranking` はGold layerで事前計算済みのランキングをそのまま返すことで、
  店舗間比較の切り口（優等生店舗／要フォロー店舗）を素早く提供する。両エンドポイントとも
  `store_id` で絞り込めるため、「特定店舗がカテゴリ構成・ランキングでどう位置づけられるか」という
  ドリルダウンにも同じAPIで対応できる。
- **データ品質フォロー（quarantine-report）**: `gold_unregistered_master_report` をそのまま
  `issue_type` 別に閲覧できるようにすることで、マスター未登録（店舗未登録・商品未登録等）の
  取引を運用担当者が定期的に確認し、マスタ登録・データ修正のフォローアップにつなげられる。
  店舗別に絞り込めるため、特定店舗のオペレーション品質（マスタ登録の運用が徹底されているか）の
  トラッキングにも使える。
- 全エンドポイント共通で `store_id` フィルタを一次市民として設計してあるため、Phase 3で店舗別
  アクセス制御（どのユーザーがどの店舗を見られるか）を追加する際、クエリ層を変更せずアプリ層で
  「ユーザーの許可店舗 ∩ リクエストのstore_id」を計算してこのAPIに渡すだけで対応できる。

## Serverless SQL Warehouseの利用方法とFree Editionへの適合性

- `db.py` は `databricks-sdk` の `Config()` を使って認証情報（ホスト・トークン/OAuth）を環境変数から
  自動解決し、`databricks-sql-connector` で `http_path=/sql/1.0/warehouses/{DATABRICKS_WAREHOUSE_ID}`
  に接続する。ローカル開発時は `DATABRICKS_TOKEN`（PAT）、Databricks Appsとしてデプロイされた際は
  アプリのサービスプリンシパルによるOAuth M2Mが自動的に使われるため、コード変更なしで両方の環境に対応する。
- クエリは全てパラメータバインド（`:param_name` のNATIVEパラメータ方式）で発行しており、
  フィルタ値をSQL文字列に直接埋め込まない（SQLインジェクション対策）。
- **Serverless SQL WarehouseがFree Editionに適している理由**: Serverless Warehouseはクエリが
  ない間は自動停止し、リクエストが来た際に数秒で起動するため、常時起動のクラスタ/Pro Warehouseと
  比べて待機コストがかからない。本デモのような低頻度・小規模なアクセスパターン（デモ利用、
  ダッシュボードの散発的な閲覧）では、Free Editionの制約下でも「使った分だけ」の課金で運用でき、
  かつクラスタサイジングやウォームプールの管理をユーザー側で行う必要がない。今回の5エンドポイントは
  いずれもGold layer上の軽量な集計・フィルタクエリであり、Serverless Warehouseの自動スケール・
  自動停止という特性と噛み合っている。

## 次フェーズへの申し送り

- 上記「未検証の前提」に記載の `DESCRIBE TABLE` 確認とWarehouseへの実クエリ確認を、
  Databricksワークスペースに到達可能な環境で実施し、必要であれば `schema_assumptions.py` を修正すること。
- Phase 3（店舗別アクセス制御）は、`store_id` フィルタを引き回す設計を前提に実装可能な状態。
