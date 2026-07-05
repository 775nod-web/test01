# 小売 Gold Layer Serving App

Gold layer（`gold_daily_store_sales` / `gold_category_sales` / `gold_store_ranking` /
`gold_unregistered_master_report`）のデータを、店舗・商品企画・データサイエンスチーム
向けに閲覧できるダッシュボードとして提供するServing layerアプリです。

- **フロントエンド**: TypeScript + React（Vite）。Streamlitは使用していません。
- **バックエンド**: FastAPI（Python）。Databricks SQL Warehouseに接続し、Gold layerの
  4表をREST APIとして配信します。
- **ホスティング**: Databricks Apps（ローカル/他クラウドにはデプロイしません）。
- **接続先Warehouse**: Serverless Starter Warehouse（`50153ad923fecd73`）

## アーキテクチャ

```
┌─────────────────────────── Databricks Apps ───────────────────────────┐
│                                                                        │
│   React(TS)フロントエンド(ビルド済み静的ファイル)                     │
│            │  fetch('/api/...')                                       │
│            ▼                                                          │
│   FastAPIバックエンド（単一プロセス。/api/* + 静的ファイル配信）      │
│            │  databricks-sql-connector                                │
│            ▼                                                          │
│   Serverless Starter Warehouse (50153ad923fecd73)                     │
│            │  SELECT ...                                              │
│            ▼                                                          │
│   gold.gold_daily_store_sales / gold_category_sales /                 │
│   gold_store_ranking / gold_unregistered_master_report                │
└─────────────────────────────────────────────────────────────────────┘
```

Databricks Appsは単一コマンドでプロセスを起動する前提のため、FastAPIが
API配信とビルド済みフロントエンドの静的配信を両方兼ねる構成にしています
（`backend/main.py`）。

## なぜこの構成か（サービス選定）

- **Databricks Apps**を選んだ理由: ビジネス目的は「店長・本社営業管理・商品企画・
  データサイエンスチームがGold layerの集計結果を継続的に閲覧する」ことであり、
  都度SQLを書く／ノートブックを開く運用は現場向けではありません。Databricks Apps は
  Databricks内でホスティングが完結し、Unity Catalog/ワークスペース権限をそのまま
  流用できるため、追加のインフラ（別クラウドのWebサーバー等）を持たずに済みます。
- **Databricks SQL（Serverless Starter Warehouse）**を選んだ理由: Gold layerは
  すでにDelta形式で確定した集計結果であり、複雑な変換は不要です。軽量なSQL
  Warehouseで十分にダッシュボードの応答性能を満たせ、Serverlessなので使わない
  時間帯はコストがかかりません。
- ダッシュボード自体はNotebookではなくカスタムAPP（FastAPI + React）にしたのは、
  Streamlit不可の制約と、店長・本社向けの「業務アプリらしいUI」を実現するためです。

## ディレクトリ構成

```
serving_app/
├── app.yaml              # Databricks Apps起動設定
├── requirements.txt       # バックエンド依存関係
├── backend/
│   ├── main.py            # FastAPIエントリポイント（API + 静的配信）
│   ├── db.py               # Databricks SQL Warehouseへの接続
│   └── queries.py          # gold.*表に対するSELECT
├── frontend/
│   └── src/
│       ├── App.tsx          # ダッシュボード全体レイアウト
│       ├── theme.css         # Google Slides風パレット（検証済み）
│       └── components/       # KPIタイル・棒グラフ・各表パネル
├── prompts/                # フェーズ毎の構築プロンプト（再現・拡張用）
└── CLAUDE.md               # このディレクトリで作業するAI向けの手引き
```

## ローカルでの動作確認

Databricks Apps上にデプロイする前に、ローカルで最低限の疎通確認ができます
（`databricks configure` 済み、または `DATABRICKS_HOST` / `DATABRICKS_TOKEN` を
環境変数で設定していること）。

```bash
# バックエンド
cd serving_app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# フロントエンド（別ターミナル）
cd serving_app/frontend
npm install
npm run dev   # http://localhost:5173 、/apiは:8000へプロキシされる
```

Databricks認証情報が無い状態でも `uvicorn` は起動し `/api/health` は
200を返しますが、Gold layerを問い合わせる `/api/*` エンドポイントは
認証エラーで500を返します（クラッシュはしません）。

## Databricks Appsへのデプロイ

このリポジトリのコード自体はこのセッションから直接デプロイできません
（このサンドボックス環境にDatabricks CLI／認証情報が無いため）。
以下はご自身のDatabricks CLI環境から実行してください。

```bash
# フロントエンドをビルドしてdist/を生成
cd serving_app/frontend
npm install
npm run build
cd ..
```

**`--source-code-path` はローカルのパスではなく、Databricksワークスペース内の
パスを指定する必要があります。** `.`（ローカルフォルダ）を渡すと
`Error: Source code path must be a valid workspace path.` になります。
先に `databricks sync` でワークスペースへコードを転送してから、そのワークスペース
パスに対して `apps deploy` を実行してください。

```bash
# 自分のワークスペースユーザー名（メールアドレス）を確認
databricks current-user me

# ローカルのserving_appをワークスペースへ同期する（1回だけでよい。
# 継続的に更新したい場合は先頭に --watch を付ける）
databricks sync . /Workspace/Users/<あなたのメールアドレス>/interviewprepretail03

# appをまだ作成していなければ作成する
databricks apps create <app-name>

# ワークスペース上のパスを指定してデプロイする
databricks apps deploy <app-name> \
  --source-code-path /Workspace/Users/<あなたのメールアドレス>/interviewprepretail03
```

デプロイ後、Databricks Apps UIの「Resources」設定で、`50153ad923fecd73`
（Serverless Starter Warehouse）へのアクセス権をアプリのサービスプリンシパルに
付与してください（`app.yaml` の `DATABRICKS_WAREHOUSE_ID` と一致させる）。
また、参照先のGold表がUnity Catalog配下にある場合は `GOLD_TABLE_PREFIX`
環境変数を `<catalog>.gold` のように上書きしてください。

### Databricks Apps数の上限に達した場合について

**このアプリ（またはどのプロンプトも）は、他のユーザーが作成したアプリを
自動的に削除しません。** 上限に達してデプロイできない場合は、
`databricks apps list` 等で既存アプリの一覧を確認し、ワークスペースの
オーナー・管理者に相談の上で対応してください。他人の成果物を無断で
削除する運用は行わないでください。

## 画面構成

1. **KPIタイル**: 総売上金額 / 総取引件数 / 店舗数 / マスター未登録取引数
2. **店舗ランキング**: 売上金額順の棒グラフ（表表示への切り替えあり）
3. **商品カテゴリ別売上**: カテゴリ別の棒グラフ
4. **日別店舗別売上**: 店舗フィルタ付きの明細表
5. **マスター未登録レポート**: 課題種別（store_id未登録／product_id未登録／両方）を
   バッジで表示する明細表

## 配色について

`frontend/src/theme.css` の配色は、Google Slidesのデフォルトカラーパレットに
近い「淡いが鮮やかな」トーンを採用しつつ、`dataviz` skillの
`scripts/validate_palette.js` でlight/dark両モードの以下4項目を検証済みです。

- Lightness band（明度帯）
- Chroma floor（彩度下限。グレーに見えないか）
- CVD separation（色覚多様性を考慮した隣接色の識別性）
- Contrast vs surface（背景とのコントラスト）

検証コマンド例（dataviz skillのディレクトリから実行）:

```bash
node scripts/validate_palette.js \
  "#4a86c6,#cc4125,#e8a317,#6aa84f,#8e7cc3,#d5793b,#1b9c9c" --mode light
node scripts/validate_palette.js \
  "#3d7dc9,#d9534f,#b8860b,#5e9e48,#7c68b8,#c96a2e,#0f9e9e" --mode dark
```
