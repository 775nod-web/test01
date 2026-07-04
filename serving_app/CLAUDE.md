# CLAUDE.md — serving_app

このディレクトリは、小売メダリオンアーキテクチャの **Gold layerを配信する
Serving layerアプリ**です。今後このディレクトリで作業するAIエージェント向けの
手引きです。

## プロジェクトの目的

`gold.gold_daily_store_sales` / `gold.gold_category_sales` /
`gold.gold_store_ranking` / `gold.gold_unregistered_master_report` の4表を、
本社営業管理・店長・商品企画・データサイエンスチームが閲覧できる
ダッシュボードとして提供する。データの生成・集計（Bronze/Silver/Gold layer）は
リポジトリ直下の `generate_retail_medallion_sample_data.py` 以降の一連の
スクリプトが担当しており、本アプリは**読み取り専用**でGold layerを配信するのみ。
Gold layer側のスキーマ・集計ロジックはここでは変更しない。

## 絶対に守ること

1. **フロントエンドはTypeScript + React（Vite）。Streamlitは使わない。**
2. **最終的なデプロイ先はDatabricks Appsのみ。** ローカルサーバーや他クラウド
   （Vercel/Netlify/AWS等）への恒久的なデプロイは行わない。ローカル起動は
   動作確認目的のみに限る。
3. **他ユーザーが作成したDatabricks Appsを自動的に削除しない。** アプリ数の
   上限に達した場合でも、削除は必ず人間（ワークスペース管理者やアプリ所有者）の
   明示的な確認を経てから行う。これはどのプロンプト・フェーズドキュメントに
   対しても優先されるガードレール。
4. Serverless Starter Warehouse ID は `50153ad923fecd73`。`app.yaml` の
   `DATABRICKS_WAREHOUSE_ID` で管理する。変更する場合はREADMEも合わせて更新する。
5. UIの配色はGoogle Slides風の「淡いが鮮やかな」パレット
   （`frontend/src/theme.css`）を使う。新しい色を追加する場合は
   `dataviz` skillの `scripts/validate_palette.js` で
   light/darkの両方を再検証してから採用する（目視だけで決めない）。

## アーキテクチャ上の制約

- Databricks Appsは単一コマンドでの起動が前提のため、FastAPI
  （`backend/main.py`）がAPI配信とビルド済みフロントエンド（`frontend/dist`）の
  静的配信の両方を兼ねる。フロントエンドとバックエンドを別プロセス・別アプリに
  分割しない。
- `backend/db.py` の `Config()` は**遅延初期化**にしてある
  （`_get_config()` を呼ぶまでインスタンス化しない）。モジュールimport時に
  即座に認証解決をしようとすると、Databricks認証情報が無い環境
  （ローカル開発やCIでの単体テスト）でアプリ全体がクラッシュするため。
  この遅延パターンは崩さないこと。
- Gold表は2階層名（`gold.gold_daily_store_sales` 等）で参照する。
  Unity Catalogでカタログ修飾が必要な環境向けに、テーブル名は
  `db.qualified_table()` 経由でのみ組み立て、クエリ内にハードコードしない
  （`GOLD_TABLE_PREFIX` 環境変数で上書き可能にするため）。

## 開発・検証の進め方

- バックエンドの構文・importチェック: `python3 -m py_compile backend/*.py`
- フロントエンドのビルド確認: `cd frontend && npm install && npm run build`
  （`tsc -b` を含むため型エラーもここで検出できる）
- Databricks資格情報が無い状態でも `uvicorn backend.main:app` は起動でき、
  `/api/health` は200を返す。`/api/*` のGold layer系エンドポイントは
  認証エラーで500になるが、プロセスはクラッシュしない（これが正しい挙動）。
- 実際のwarehouse接続・SQLクエリの正しさは、このセッションからは検証できない
  （Databricks資格情報が環境に無いため）。コードレビューでは
  「クエリが`gold.*`の実カラム名と一致しているか」「型変換
  （date/Decimal→JSON）が漏れていないか」を重点的に確認する。

## ディレクトリを拡張する時の指針

- 新しいGold表・新しいAPIエンドポイントを追加する場合は
  `backend/queries.py` に関数を1つ追加し、`backend/main.py` に薄い
  ルートハンドラを1つ追加する形を踏襲する（クエリロジックをmain.pyに
  書かない）。
- フロントエンドの新しいパネルは `frontend/src/components/` に1コンポーネント
  1ファイルで追加し、`App.tsx` から呼び出す。データ取得は
  `frontend/src/api.ts` にラッパー関数を追加してから使う（コンポーネント内で
  直接 `fetch` しない）。
- 新しいカテゴリ配色が必要になった場合（8系列目以降）は、固定順で循環させず
  `var(--text-muted)` 等へフォールドする（`dataviz` skillの非交渉ルール）。

## フェーズ別プロンプト

`prompts/` 配下に、このアプリをフェーズごとに構築するためのプロンプトを
保存している。ゼロから再構築する場合や、大きな機能追加をする場合は
該当フェーズのプロンプトを参考にすること。
