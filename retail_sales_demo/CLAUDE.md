# CLAUDE.md — 小売POS売上分析デモ（Serving Layer / Databricks Apps）

このファイルは、本デモを実装するコーディングエージェント（Databricksワークスペースに接続されたClaude Code等）向けの運用ルールです。`prompts/` 配下のフェーズプロンプトを実行する際は、必ず本ファイルの制約を優先してください。

## プロジェクトの目的

大手小売企業の顧客シナリオに基づき、Gold layer（Unity Catalog上のDelta テーブル）のデータを、TypeScript + Reactで構築したUIから閲覧できるようにする **Serving layer** を、Databricks Free Edition上に構築する。最終成果物は Databricks Apps 上で稼働するフルスタックアプリケーション。

## 絶対的な制約（違反しないこと）

- **ホスティングは Databricks Apps のみ。** ローカル環境やその他のホスティングサービスにアプリを作成してはならない。
- **フロントエンドは TypeScript + React。Streamlit は使用禁止。**
- **Serverless SQL Warehouseは `50153ad923fecd73`（Serverless Starter Warehouse）を使用する。** 新規Warehouseを作成しない。
- Databricks Free Edition で提供されない機能（専用クラスタ、リアルタイムModel Serving等）を前提とした実装をしない。実演できない範囲は「口頭説明」として明記し、コードでの実装は行わない。
- UIの配色は下記「デザイントークン」に従う。
- **READMEファイルを作成すること。**（デプロイ手順・前提条件・デモ操作手順を含む）

## Databricks Apps 上限到達時の対応（重要・要ユーザー確認）

Databricks Free Editionでは、ワークスペースごとに作成可能なDatabricks Appsの数に上限がある。新規アプリ作成時に上限エラーが出た場合の手順：

1. Databricks Apps一覧を取得し、作成日時が最も古いアプリを特定する。
2. **削除対象アプリの名前・作成者・作成日時を必ずユーザーに提示し、明示的な削除承認を得てから削除を実行する。** 他ユーザーが作成したアプリを削除する操作は影響範囲が大きい破壊的操作のため、たとえ本タスクの依頼内容に「削除してよい」という一般的な許可が含まれていても、実際に削除する直前には必ず一度確認を挟むこと。
3. 承認後、当該アプリを削除してから本デモアプリを新規作成する。

## Gold layer スキーマ（参照用・変更しないこと）

Serving layerはこれら4テーブルを読み取り専用で利用する。

**実ワークスペースで確認済みのカタログ/スキーマ**:
- Gold layer: `workspace.gold`（例: `workspace.gold.gold_daily_store_sales`）
- Silver layer（マスター参照用、quarantine再照合ジョブが利用）: `workspace.silver.silver_product_master` / `workspace.silver.silver_store_master`

デモ用データは店舗5件・カテゴリ4件・POS取引230件（うちマスター未登録10件）という小規模なサンプルであり、これがFree Edition上での実演スケールとなる。「1時間あたり数千万〜1億件」という本番スケールは口頭説明のみで対応する（README.mdの優先度表を参照）。

## ガバナンス機能の検証結果（重要）

`workspace.gold` に対してUnity Catalogの行フィルタ（ROW FILTER）・列マスキング（COLUMN MASK）をSQLエディタで実行し、**Free Editionで構文エラーなく動作すること、列マスキングが実際に効くこと（customer_idが`MASKED`表示になること）を確認済み**（`app/sql/ready_to_run_step2.sql`）。

ただし、この確認はSQLエディタ上で「人間が自分の資格情報で」実行した結果であり、`current_user()` がその人自身に解決されたために機能した。Databricks Appsからのクエリは既定でアプリのサービスプリンシパルとして実行されるため、**User Authorization（on-behalf-of-user）を有効化しない限り、行フィルタ・列マスキングはアプリ利用者ごとには機能しない**（全利用者がサービスプリンシパルの権限で一律に同じ結果を見ることになる）。したがって:

- `app.yaml` の `ROW_FILTER_ENABLED_BY_UC` は、on-behalf-of-user認証をデプロイ後に実際に検証するまで `false` のままにし、店舗別アクセス制御はバックエンドのAPI側フィルタ（`user_store_mapping`参照）を正とする。
- Phase 4（デプロイ）で on-behalf-of-user を有効化し、実際にアプリ経由で `current_user()` がエンドユーザーに解決されることを確認できた場合のみ `true` に切り替える。

### `gold_daily_store_sales`（粒度: sales_date × store_id）
| 列名 | 型 | 説明 |
|---|---|---|
| sales_date | DATE | 売上日 |
| store_id | STRING | 店舗ID |
| store_name | STRING | 店舗名 |
| region | STRING | 地域 |
| transaction_count | BIGINT | 取引件数（重複除去済み） |
| total_quantity | BIGINT | 販売数量合計 |
| total_sales_amount | DOUBLE | 売上金額合計（discount控除後のnet想定） |

### `gold_category_sales`（粒度: category）
| 列名 | 型 | 説明 |
|---|---|---|
| category | STRING | 商品カテゴリ |
| product_count | BIGINT | カテゴリ内のマスター登録商品数 |
| transaction_count | BIGINT | 取引件数 |
| total_quantity | BIGINT | 販売数量合計 |
| total_sales_amount | DOUBLE | 売上金額合計 |

### `gold_store_ranking`（粒度: store_id、累計＋ランキング）
| 列名 | 型 | 説明 |
|---|---|---|
| sales_rank | INT | 売上順位 |
| store_id / store_name / region / store_type | STRING | 店舗属性 |
| total_sales_amount | DOUBLE | 売上金額合計 |
| total_quantity | BIGINT | 販売数量合計 |
| transaction_count | BIGINT | 取引件数 |

### `gold_unregistered_master_report`（粒度: transaction_id、マスター未登録取引のみ）
| 列名 | 型 | 説明 |
|---|---|---|
| transaction_id | STRING | 取引ID |
| issue_type | STRING | 未登録種別（store_id未登録／product_id未登録／両方） |
| store_id / product_id / customer_id / transaction_datetime | STRING(NULL可) | 取引の生値 |
| is_store_registered / is_product_registered | BOOLEAN | マスター登録有無フラグ |
| quantity / unit_price / discount_amount / sales_amount | INT/DOUBLE(NULL可) | 数量・金額情報 |

> **既知のギャップ**: `gold_daily_store_sales` と `gold_category_sales` にはdiscount集約列がなく、gross salesを正確に算出できない。Serving layerでは `total_sales_amount` をnet salesとして扱い、gross salesは注記付きの暫定表示とする。Gold layerへの列追加は本タスクのスコープ外。

## デザイントークン（Google流スライド風パステルカラー）

```
--color-primary:   #AECBFA;  /* Pastel Blue - 通常データ、プライマリボタン */
--color-positive:  #A8DAB5;  /* Pastel Green - 売上増、ポジティブKPI */
--color-negative:  #F6AEA9;  /* Pastel Coral - 売上減、アラート */
--color-warning:   #FDE293;  /* Pastel Yellow - 未登録/quarantine系 */
--color-accent:    #D7AEFB;  /* Pastel Purple - アクセント、カテゴリチャート */
--color-bg:        #F8F9FA;  /* Off White - 背景 */
--color-text:      #202124;  /* Neutral Dark - 本文 */
```

彩度を上げすぎず、カード背景は淡色、テキストは`--color-text`で統一する。カテゴリ別チャートは primary → accent → positive → warning → negative の順で色をローテーションする。

## コーディング規約

- バックエンド: Python (FastAPI推奨)。Gold テーブルへのアクセスは Databricks SQL Connector または Statement Execution API 経由、Warehouse IDは環境変数 `DATABRICKS_WAREHOUSE_ID` で注入し、コード中にハードコードしない（値は `50153ad923fecd73`）。
- フロントエンド: React + TypeScript + Vite。状態管理は必要最小限（React Query等でAPIフェッチのキャッシュのみで十分、Reduxのような大掛かりな構成は不要）。
- ディレクトリ構成の目安:
  ```
  app/
    backend/    # FastAPI等
    frontend/   # React + TS
    app.yaml    # Databricks Apps設定
  README.md
  ```
- 秘密情報（トークン等）はコードやREADMEに直書きしない。Databricks Apps のシークレット/環境変数機能を使う。

## フェーズ実行順序

`prompts/phase0_environment_setup.md` → `phase1_serving_layer_api.md` → `phase2_frontend_react_app.md` → `phase3_governance_and_alerts.md` → `phase4_deploy_databricks_apps.md` の順に実行する。各フェーズの完了条件は各プロンプトファイルの「完了条件」セクションを満たすこと。

各フェーズの実装完了時には、コードと合わせて「このフェーズがビジネス目的にどう貢献するか」「どのDatabricksサービスをどう使ったか」を短く説明すること。
