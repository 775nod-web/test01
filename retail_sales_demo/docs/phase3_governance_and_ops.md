# Phase 3: ガバナンス・アラート・自動再照合 — 結果報告

実施日: 2026-07-05

## 前提となる制約（Phase 0〜2から継続）

このコーディングエージェントセッションは、一貫してDatabricksワークスペースへのネットワーク到達性を
持たない（セッションのエグレスポリシーが `dbc-74bfd917-30ed.cloud.databricks.com` へのCONNECTを
403で拒否）。Phase 3はこの制約下で最も影響が大きいフェーズだった。3-A〜3-Cはいずれも「Unity
Catalogのネイティブ機能がFree Editionで使えるかを実際に検証してから方式を選ぶ」ことを求めていたが、
それ自体が実行不可能だったため、**ユーザーの承認を得た上で、検証を要しないフォールバック方式を
最初から採用**した（実装前にAskUserQuestionで確認済み）。

## 3-A. 店舗別アクセス制御 — フォールバック方式を採用

**採用方式: APIレイヤーでの `store_id` フィルタ（フォールバック）。UCの行フィルタ（優先案）は未検証。**

- `app/backend/access_control.py` が新規のUnity Catalogテーブル
  `workspace.silver.silver_user_store_mapping`（DDL: `sql/001_user_store_mapping.sql`）を
  `user_email` で引き、許可店舗リスト（`None`=全店舗、`[]`=アクセス不可、それ以外=許可店舗ID一覧）を
  解決する。
- 全APIエンドポイントで、リクエストの `store_id` と許可店舗リストを `resolve_effective_store_ids()`
  で積集合し、クエリを発行する前に適用する（許可店舗が空集合なら、Warehouseに問い合わせずに
  空のレスポンスを返す）。
- ユーザー識別は `X-Forwarded-Email` リクエストヘッダーから行う想定（Databricks Appsが
  ユーザー認可を設定した際にSSOのユーザーをこのヘッダーで転送すると想定しているが、**このヘッダー名も
  実環境で確認できていない**。ヘッダーが無い場合は `DEMO_USER_EMAIL` 環境変数（既定値
  `hq-demo@example.com`）にフォールバックする。

### 重要なセキュリティ上の注意

この方式は **データベースレベルの保証ではない**。FastAPIバックエンドは単一の共有サービスプリンシパル
（または開発用PAT）でWarehouseに接続しており、ユーザーごとに異なるDB認証情報を使っているわけではない。
つまり「店舗Aのユーザーが店舗Bを見られない」のはAPIコードがそう作られているからであり、同じWarehouse・
同じUnity Catalogテーブルに対して別の経路（SQLエディタ、ノートブック、別のBIツール等）で直接アクセスする
ユーザーやサービスプリンシパルには、このアクセス制御は一切効かない。真にDBレベルで保証したい場合は、
Unity Catalogの行フィルタ（ROW FILTER）機能をこのワークスペース/エディションで実際に検証し、
`gold_daily_store_sales` 等に適用する必要がある。

## 3-B. PIIマスキング — フォールバック方式を採用

**採用方式: APIレスポンス生成時のマスキング（フォールバック）。UCの列マスキング（優先案）は未検証。**

- `gold_unregistered_master_report` に `customer_id` 列がある前提を追加した
  （`schema_assumptions.py` — Phase 1では存在確認すらしていなかった列なので、この追加自体も未検証）。
- `access_control.py` の `AccessContext.can_view_pii` が、ユーザーが `PII_VIEWER` ロール
  （`workspace.silver.silver_user_role_mapping`、DDL: `sql/002_user_role_mapping.sql`）を持つか、
  admin（全店舗許可）かを判定する。
- `GET /api/quarantine-report` は `can_view_pii` が偽の場合、`customer_id` を
  `access_control.mask_customer_id()`（先頭4文字を残して残りを `*` に置換）でマスクし、
  `customer_id_is_masked: true` をレスポンスに含める。フロントエンドはこのフラグを見て
  「マスク済み」バッジを表示する。
- 実ブラウザでの確認: `PII_VIEWER` を持つ `dq-demo@example.com` では `CUST1001` がそのまま表示され、
  ロールを持たない `store1-demo@example.com` では `CUST****` + 「マスク済み」バッジ表示になることを、
  データ品質ビューの「実行ユーザー」切替で確認した。

3-Aと同じ注意が当てはまる: マスキングもAPIレイヤーで行っており、Unity Catalog上で直接クエリすれば
マスクされていない値が見える。

## 3-C. 監査ログ — フォールバック方式を採用

**採用方式: アプリ独自の軽量監査ログテーブル（フォールバック）。`system.access.audit`（優先案）は
参照可能かどうか未確認。**

- `workspace.silver.silver_app_audit_log`（DDL: `sql/003_app_audit_log.sql`）に、
  `logged_at, user_email, endpoint, store_id_filter, status_code` を記録する。
- `app/backend/main.py` の `audit_log_middleware` が `/api/*` への全リクエストについて、
  レスポンス確定後に `audit.record_access()` を呼ぶ。書き込みは `try/except` で必ず失敗を握りつぶし、
  監査ログの書き込み失敗が実際のAPIレスポンスを壊さないようにしている。
- `GET /api/audit-log` で直近ログを閲覧できる（`AUDIT_VIEWER` ロールまたはadminのみ、それ以外は403）。
  データ品質ビューに簡易な監査ログ閲覧パネルを追加した。
- 実ブラウザでの確認: `store1-demo@example.com`（ロール無し）で `/api/audit-log` を開くと
  403エラーメッセージがパネル内に表示され、`dq-demo@example.com`（`AUDIT_VIEWER`）では
  ログ一覧が表示されることを確認した。

**既知の制約**: `system.access.audit` が実際に参照可能なら、このアプリのログに写らない操作
（同じテーブルへの直接SQL/ノートブックアクセスなど）まで捕捉できるため、そちらを優先すべきである。
また、現在の実装は監査ログの書き込みをリクエスト処理と同期的に行っており、リクエストごとに
Warehouseへの追加往復が発生する（本デモの規模では許容範囲だが、実運用ではバッファリング/非同期化を
検討すべき）。

## 3-D. 売上急減しきい値アラート — コード実装済み、デプロイ未実施

- `jobs/alert_batch.py`: `gold_daily_store_sales` から店舗別の前日比（DoD）・前週比（WoW）の
  `net_sales` 変化率を計算し、しきい値 `-20%` を下回った行を `gold_store_sales_alerts` に書き込む
  （PySparkスクリプト、Databricks Jobsのタスクとして実行される想定）。
- `jobs/resources/alert_batch_job.json`: 日次06:00(Asia/Tokyo)実行のJobs API作成用テンプレート
  （`pause_status: PAUSED` で作成し、動作確認後に有効化する運用を想定）。
- `GET /api/alerts`: `gold_store_sales_alerts` の最新日付分を読むだけの薄いAPI。
- フロントエンド: 本社経営ダッシュボードの「売上急減アラート」を、Phase 2のダミー枠から
  `AlertBanner`（実際に `/api/alerts` を叩く）に置き換えた。アラート無し/取得エラー時は
  その旨を中立色で表示し、アラート発生時のみPastel Coralで警告を表示する。

**未実施（このセッションではできない）**: `alert_batch_job.json` を実際にワークスペースへ
デプロイ（`databricks jobs create --json @alert_batch_job.json`等）し、`alert_batch.py` を
実データに対して一度動かして `gold_store_sales_alerts` が正しく作られることを確認する作業。
また `alert_batch_job.json` のcompute設定（`environment_key` によるサーバーレス実行を想定した
テンプレート）はDatabricks Jobs APIの実仕様を参照せずに書いたため、その形式自体が正しいかも未検証。

## 3-E. quarantine自動再照合バッチ — コード実装済み、デプロイ未実施

- `jobs/requeue_batch.py`: `gold_unregistered_master_report` の各行を、最新の
  `silver_product_master` / `silver_store_master` と突き合わせ、「今なら解決するはずの件数
  （reconciled candidates）」を数えて `gold_requeue_batch_runs` に1行追記する。
  **明記した通り、このジョブは `gold_unregistered_master_report` からレコードを実際には
  取り除かない** — それには既存のSilver→Gold再計算パイプラインの再実行が必要であり、
  本Serving layer実装のスコープ外である。
- `GET /api/requeue-status`: 直近実行の件数・ステータスを返す。
- `POST /api/requeue-trigger`: Databricks Jobs API（`WorkspaceClient().jobs.run_now`）で
  `jobs/requeue_batch.py` のジョブを起動する。**`REQUEUE_JOB_ID` が未設定の間はHTTP 501を返し、
  成功したふりはしない**（ジョブが未デプロイであることが実際の状態のため）。
- フロントエンド:「再照合を実行」ボタンはPhase 2の純粋なダミーから、実際に
  `POST /api/requeue-trigger` を呼ぶ実装に変わった。バックエンドが501を返す間は、その
  エラーメッセージ（「REQUEUE_JOB_ID が未設定です…」）をそのままUIに表示する。
  データ品質ビューには `/api/requeue-status` から取得した直近実行のサマリー
  （実行日時・ステータス・チェック件数・再照合候補数）も表示する。

**未実施**: `requeue_batch_job.json` の実デプロイ、ジョブID取得、`REQUEUE_JOB_ID` 環境変数への設定、
実データに対する初回実行確認。

## 動作確認の内容

Phase 1/2と同様、実Warehouse/実データに対する検証はできない。以下は実施済み:

1. `pytest`: 42件（既存30件 + Phase 3新規12件）が全てPASS。
   - `test_access_control.py`: 店舗ID積集合ロジック（許可なし/一部重複/重複なし/admin全許可）、
     `customer_id` マスキング、`can_view_pii` / `can_view_audit_log` の役割判定。
   - `test_queries.py`: 新規クエリビルダー（マッピング参照、監査ログINSERT/SELECT、アラート、
     再照合ステータス）のSQL/パラメータ組み立て。
   - `test_governance_api.py`: アクセス制御が実際にWarehouseへ問い合わせる前に拒否すること、
     許可店舗との積集合、PIIマスキングのON/OFF、監査ログの403、`/api/requeue-trigger` の501。
2. `run_query` と `access_control.get_access_context` の両方をモックしたFastAPIサーバーを起動し、
   ビルド済みSPAと共にPlaywright（Chromium）で実ブラウザ検証:
   - 本社経営ダッシュボードで実際の `/api/alerts` からのアラートバナー表示を確認。
   - 店舗ビューで「ログインシミュレーション」を切り替えると `/api/me` が返す許可店舗が
     画面に反映されることを確認。
   - データ品質ビューで「実行ユーザー」を切り替えると、`customer_id` のマスク表示/非表示が
     連動して切り替わることと、監査ログパネルが403エラーを適切に表示することを確認。
   - 「再照合を実行」ボタンをクリックすると、`POST /api/requeue-trigger` の501エラーメッセージが
     そのままUIに表示されることを確認（ジョブ未デプロイの現状を偽らずに反映）。

## Free Editionで確認できなかった項目のまとめ

| 項目 | 優先案 | 状態 |
|---|---|---|
| 3-A 行レベルセキュリティ | Unity Catalog ROW FILTER | 未検証。フォールバック（APIレイヤー）を採用 |
| 3-B 列マスキング | Unity Catalog列マスク | 未検証。フォールバック（APIレスポンス生成時マスキング）を採用 |
| 3-C 監査ログ | `system.access.audit` | 未検証。フォールバック（アプリ独自監査テーブル）を採用 |
| 3-D/E Jobs API | サーバーレスJob compute（`environment_key`によるテンプレート） | JSON仕様自体が未検証。デプロイ未実施 |

これらは全て、Databricksワークスペースに到達可能な環境から以下の手順で検証・デプロイする必要がある:

1. `sql/001_user_store_mapping.sql` 〜 `003_app_audit_log.sql` を実行し、実ユーザーのメールアドレスに
   合わせて `user_email` の値を差し替える。
2. `DESCRIBE TABLE workspace.gold.gold_unregistered_master_report` で `customer_id` 列の実在と
   実際の列名を確認する。
3. UC ROW FILTER / 列マスク / `system.access.audit` の利用可否を確認し、使えるなら3-A〜3-Cの
   フォールバックをネイティブ機能に置き換えることを検討する。
4. `jobs/resources/alert_batch_job.json` / `requeue_batch_job.json` を実際の compute設定に合わせて
   修正し、`databricks jobs create` でデプロイ。`requeue_batch_job.json` 側のjob_idを
   `REQUEUE_JOB_ID` 環境変数に設定する。
5. 両バッチを一度手動実行し、`gold_store_sales_alerts` / `gold_requeue_batch_runs` が
   想定通り作られることを確認する。

## ガバナンス実装が要件をどう満たすか

- **店舗別アクセス制御**: 全APIエンドポイントが「リクエストされたstore_id」ではなく
  「サーバー側で解決した許可store_id」に基づいてクエリを発行するため、フロントエンドが
  何を送ってきても、許可されていない店舗のデータが返ることはない（クエリを発行する前に
  空集合なら即座に空レスポンスを返す設計）。ただし前述の通り、これはアプリケーション層の保証であり、
  同一WarehouseへのDB直アクセスには及ばない。
- **PIIマスキング**: `customer_id` は既定でマスクされ、`PII_VIEWER` ロールを持つ利用者のみ生値を見られる。
  マスク済みかどうかを `customer_id_is_masked` として明示的にレスポンスへ含めているため、
  フロントエンドが誤って生値と誤認して表示することがない。
- **監査ログ**: 全APIアクセスが「誰が・どのエンドポイントに・どの店舗フィルタで・いつ・
  どんなステータスで」アクセスしたかを記録し、`AUDIT_VIEWER`/adminのみが閲覧できる簡易画面を用意した。
  これにより、店舗別アクセス制御やPIIマスキングが実際にどう使われているかを事後的に追跡できる。

## アラート・自動再照合が顧客の現行課題にどう応えるか

- **処理の遅さ（早期把握の欠如）への対応**: 従来、売上急減は本社担当者が手動でダッシュボードを
  見て気づくか、もっと遅れて月次レポートで発覚していたと想定される。`gold_store_sales_alerts` を
  日次バッチで機械的に生成し、`/api/alerts` 経由で本社ダッシュボードに常時表示することで、
  「気づくまでの時間」を最大1日（バッチの実行頻度）に短縮する設計にした。しきい値判定を
  DoD/WoWの2種類で行うため、突発的な落ち込みと、曜日変動を考慮した傾向的な落ち込みの両方を拾える。
- **再処理の手間（quarantine対応の煩雑さ）への対応**: 従来、マスター未登録取引が実際に解決したかどうかは
  誰かが手動でGold layerを再確認するまで分からなかったと想定される。`requeue_batch.py` が
  「今なら解決するはずの件数」を自動的に可視化することで、データ品質チームは「もう一度パイプラインを
  回す価値があるか」を毎回手動で調べずに判断できるようになる。「再照合を実行」ボタンから
  Jobs APIを直接叩けるようにしたことで、確認から再照合トリガーまでの導線を1画面に集約した
  （ただし実際のGold再計算は既存パイプラインの責務であり、このボタンが起動するのはあくまで
  「候補件数を数え直す」バッチである点に注意）。

## 次フェーズへの申し送り

- 上記「Free Editionで確認できなかった項目」の1〜5を、Databricksワークスペースに到達可能な
  環境で実施すること。
- 3-A/3-B/3-Cのフォールバックが、優先案（UCネイティブ機能）でも代替可能か再評価すること。
