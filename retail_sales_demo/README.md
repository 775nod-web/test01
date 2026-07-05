# 小売POS売上分析デモ — Serving Layer & Databricks Apps

大手小売企業向け「店舗別・商品カテゴリ別売上分析」デモの設計書です。顧客シナリオと Gold layer 設計を起点に、Serving layer（Gold → API → UI）の実装内容、追加提案機能とその根拠・優先度、45分の説明会（デモ15分）の構成、Databricks Free Edition 上で使用するサービスの選定理由をまとめています。

実装は本ドキュメントおよび `prompts/` 配下のフェーズ別プロンプトを、Databricksワークスペースに接続されたコーディングエージェント（Claude Code on Databricks 等）に順番に投入することで進めます。**このリポジトリ内での直接のPySpark/Databricksワークスペース操作は行わず、依頼用プロンプトと設計ドキュメントの整備までを本タスクのスコープとします。**

---

## 1. 前提条件（実装前に必ず確認）

| 項目 | 値 |
|---|---|
| Databricks 環境 | Databricks Free Edition |
| Serverless SQL Warehouse | `Serverless Starter Warehouse`（ID: `50153ad923fecd73`） |
| フロントエンド | TypeScript + React（Streamlit禁止） |
| アプリホスティング | Databricks Apps のみ（ローカル実行不可） |
| Gold layer | 顧客シナリオに基づき設計済み（`gold_daily_store_sales` / `gold_category_sales` / `gold_store_ranking` / `gold_unregistered_master_report`） — 本タスクでは既存とみなし、Serving layer のみを新規実装する |

> **重要な設計上のギャップ**: KPI要件には `net sales` と `gross sales` の両方が含まれますが、現行の Gold スキーマには discount（値引）の集約列が存在せず、`total_sales_amount` のみが保持されています。そのため Serving layer 単独では gross/net を正確に分離できません。本デモでは `total_sales_amount` を net sales として表示し、gross sales は「discount_amount 集約列が Gold layer に追加され次第、正確な値に更新予定」という注記付きの暫定値（= net sales と同値、またはハイフン表示）とします。これは口頭でも明示的に説明すべき既知の制約です。

---

## 2. ビジネス目的とアーキテクチャの整合性

顧客シナリオの各要求と、Serving layer 設計のどこで応えるかを対応付けます。

| 顧客シナリオの要求 | Serving layer での対応 | 実装区分 |
|---|---|---|
| 店舗・商品別売上の可視化、売上低下の早期把握 | `gold_daily_store_sales` を時系列チャート化＋前日比しきい値アラート | 必須＋追加(高) |
| ユーザー別の閲覧ニーズ（本社/店長/商品企画/DSチーム） | ロール別ダッシュボード4画面（本社経営／店舗／商品企画／データ品質） | 必須 |
| 重複transaction/未登録ID/discount null/時刻形式不一致 | Gold layer側で吸収済みの値を正として表示し、未登録分は `gold_unregistered_master_report` を専用画面で可視化 | 必須 |
| マスター未登録データを落とさずquarantine管理 | 未登録レポート画面＋issue_type別フィルタ＋再照合バッチ連携 | 必須＋追加(高) |
| 店舗別アクセス制御・PIIマスキング・監査ログ | Unity Catalog行フィルタ／列マスキング＋アプリ内監査ログ | 必須（一部Free Edition制約あり） |
| REST APIでの取得が遅く、マスター更新遅延で再処理が必要 | 未登録レコードの自動再照合ジョブ（マスター更新を検知して自動昇格） | 追加(高) — 現場の隠れた苦労に対する提案 |
| KPI: net sales / gross sales / transaction count / units sold / average basket size | KPIサマリーAPI・カード表示（gross salesは上記ギャップに注記） | 必須 |
| ML活用は最後（優先度低） | 需要予測等はスコープ外、口頭説明のみ | Free Editionでは実演せず |

**設計がビジネス目的を達成できているかの説明**: Gold layer が既に「日次×店舗」「カテゴリ」「ランキング」「未登録」という4つの分析軸を粒度分離して提供しているため、Serving layerはこれをそのままAPI化するだけで「早期把握」「傾向把握」「データ品質フォロー」という3つのビジネス目的に直結します。追加のアラート機能と自動再照合機能を組み合わせることで、単なる可視化（受動的）から、運用改善（能動的）への価値ジャンプを提示できる設計になっています。

---

## 3. Databricks Free Edition 利用サービスと役割

| サービス | 役割 | 選定理由 |
|---|---|---|
| Unity Catalog | Gold Delta テーブルのガバナンス（権限、行フィルタ、列マスキング） | Free Editionでも利用可能な唯一の統合ガバナンス基盤。店舗別アクセス制御・PIIマスキング要件に直接対応 |
| Delta Lake（Gold テーブル） | Serving layerのデータソース | ACID・スキーマ強制により、Serving layer側でのデータ不整合ハンドリングが不要になる |
| Serverless SQL Warehouse（`50153ad923fecd73`） | Serving layerのクエリエンジン | クラスタ管理不要・自動スケール・秒課金で、デモ用途のコスト効率が高い。指定済みのWarehouse IDをそのまま利用 |
| Databricks Apps | React(TS)フロントエンド＋バックエンドAPIの単一ホスティング環境 | 要件で明示されたホスティング先。OAuthによるユーザー認証をUnity Catalog権限にそのまま連携できるため、店舗別アクセス制御の実装が容易 |
| Databricks Jobs（Workflows） | しきい値アラート算出バッチ、quarantine自動再照合バッチ | サーバレスジョブとしてFree Editionでも実行可能。UIからの手動トリガーにも対応 |
| System Tables（`system.access.audit` 等） | 監査ログの参照（利用可否は要検証） | Free Editionでの提供範囲に制約がある可能性があるため、フォールバックとしてアプリ内の独自監査ログテーブルを併用 |

Free Editionで**明示的に使用しないサービス**: Model Serving（リアルタイム推論エンドポイント）、専用クラスタ、Delta Live Tables の本番運用機能、外部システム連携（Partner Connect等）。これらはFree Editionでの提供が無い、または大規模本番運用を前提としており、今回のデモスコープ外です。

---

## 4. 追加機能の提案（顧客が気づいていない課題への対応）

顧客シナリオの「現行」欄（REST APIが遅い、マスター更新遅延で再処理が必要）と「その他」欄（未登録データをquarantine管理）から、以下の"現場の苦労"を推定し、機能として提案します。

| # | 追加機能 | 推定される隠れた課題 | 提案根拠 |
|---|---|---|---|
| 1 | **quarantine自動再照合バッチ** | マスター更新のたびにエンジニアが手動で再処理を実行している | 顧客シナリオに明記された「マスター更新遅延で再処理が必要」を自動化すれば、データエンジニアの定常作業を削減し、「未登録データを落とさず管理」という要件を運用面まで完成させられる |
| 2 | **売上急減しきい値アラート** | 店長・本社担当が日次で手動チェックしないと売上低下に気づけない | ビジネス目的そのものが「売上低下の早期把握」であり、閲覧型ダッシュボードだけでは"見に行かないと気づけない"という運用ギャップが残る |
| 3 | **データ品質ヘルスダッシュボード（quarantine率の推移）** | データサイエンスチームがデータ品質の改善傾向を都度SQLで確認している | 未登録レポートは「今の状態」のスナップショットに留まるため、時系列のquarantine率を可視化することで品質改善施策の効果測定に使える |
| 4 | **会員/非会員のバスケット比較** | 顧客/会員データソースが定義されているが、現行Gold設計では未活用 | 将来のマーケティング施策評価につながるが、必須KPIには含まれないため優先度は低い |
| 5 | **監査ログ閲覧UI** | 「誰がどの店舗データを見たか」を追跡する手段が現場にない | ガバナンス要件の「監査ログ」を実際に運用者が確認できる形にすることで、コンプライアンス対応の実務を支援 |

---

## 5. 実装優先度

| 機能 | 優先度区分 |
|---|---|
| Gold→API化（4テーブル）、ロール別ダッシュボードUI、KPIサマリー表示 | **必須（要件）** |
| 店舗別アクセス制御（行フィルタ）、PIIマスキング（列マスキング） | **必須（要件）**※Free Editionでの機能提供範囲は実装時に要検証、フォールバックはFilteredビュー |
| quarantine自動再照合バッチ | **追加機能・優先度高** |
| 売上急減しきい値アラート | **追加機能・優先度高** |
| データ品質ヘルスダッシュボード（quarantine率推移） | **追加機能・優先度中** |
| 監査ログ閲覧UI | **追加機能・優先度中**（Free Edition制約により簡易実装） |
| 会員/非会員バスケット比較 | **追加機能・優先度低** |
| リアルタイムMLモデルサービング（需要予測等） | **Free Editionでは実装不可 → 口頭説明のみ** |
| 本番スケール（数千万〜1億件/時）のストリーミング実演 | **Free Editionでは実装不可 → 口頭説明のみ（小規模サンプルデータで代替）** |
| 外部システムとの本番REST常時連携 | **Free Editionでは実装不可 → 口頭説明のみ** |
| 監査ログの長期保持・Delta Sharingでの外部共有 | **Free Editionでは実装不可 → 口頭説明のみ** |

---

## 6. デモ構成（説明45分／デモ15分）

| 時間 | 内容 |
|---|---|
| 0:00–0:05 | オープニング：顧客課題の再確認、本日のゴール共有 |
| 0:05–0:15 | アーキテクチャ全体像の説明（Bronze/Silver/Goldの前提、データ品質対応方針、Databricksサービスの役割） |
| **0:15–0:30（デモ15分）** | **本編デモ** |
| 　0:15–0:18 | 本社営業管理ビュー：全社KPIサマリー＋日別店舗売上推移＋売上急減アラート |
| 　0:18–0:20 | 店長ビュー：自店舗のみに制限されたアクセス制御画面（ガバナンスデモ） |
| 　0:20–0:23 | 商品企画ビュー：カテゴリ別売上・店舗ランキング |
| 　0:23–0:27 | データ品質ビュー：未登録マスターレポート、quarantine率推移、再照合ボタン実行→反映確認 |
| 　0:27–0:30 | KPI達成状況のまとめ |
| 0:30–0:40 | 追加機能ロードマップの説明、Free Editionでの制約範囲（口頭説明項目）の整理 |
| 0:40–0:45 | Q&A |

---

## 7. UIデザイン方針（Google流スライド風パステルカラー）

淡く鮮やかな配色を、役割・状態に応じて一貫して使用します（詳細トークンは `CLAUDE.md` を参照）。

| 用途 | カラー名 | HEX |
|---|---|---|
| プライマリ（ブルー） | Pastel Blue | `#AECBFA` |
| ポジティブ（売上増） | Pastel Green | `#A8DAB5` |
| ネガティブ（売上減・アラート） | Pastel Coral | `#F6AEA9` |
| 注意（未登録・quarantine） | Pastel Yellow | `#FDE293` |
| アクセント | Pastel Purple | `#D7AEFB` |
| 背景 | Off White | `#F8F9FA` |
| 本文テキスト | Neutral Dark | `#202124` |

---

## 8. 実装の進め方

`prompts/` 配下のプロンプトを、Databricksワークスペースに接続されたコーディングエージェントへ**フェーズ順に**投入してください。各プロンプトは実行結果として「コード」と「ビジネス目的への整合性・使用サービスの説明」の両方を出力するよう指示しています。

1. `prompts/phase0_environment_setup.md` — 環境確認、Warehouse/Catalog確認、Databricks Apps上限チェック
2. `prompts/phase1_serving_layer_api.md` — Gold→APIのバックエンド実装
3. `prompts/phase2_frontend_react_app.md` — TypeScript+ReactによるロールベースUI実装
4. `prompts/phase3_governance_and_alerts.md` — 行フィルタ／列マスキング／監査ログ／アラート／自動再照合
5. `prompts/phase4_deploy_databricks_apps.md` — Databricks Appsへのデプロイ、README生成

プロジェクト運用ルール・制約・Goldスキーマ定義は `CLAUDE.md` に集約しています。
