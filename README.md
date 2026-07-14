# Fraud Decision Center（不正対策デモ）

不正リスクを見抜き、正常な顧客体験と事業成長を守る——国内のモバイル決済・デビットカード事業者向けに、
不正対策の将来業務を体験してもらう日本語デモアプリです。

> 本アプリはデモ用の合成データを使用しています。実際の取引判定や顧客データは含まれません。

現時点はPhase 1（アプリ基盤と合成データAPI）までの実装です。経営ダッシュボード(Fraud Command Center)と
調査ワークベンチ(Investigation Workbench)の本格的なUIはPhase 2・Phase 3で実装します。

---

## 技術構成

```text
Databricks Apps (1 App / 1 Pythonプロセス)
└── uvicorn main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT}
    └── FastAPI (backend/)
        ├── /api/health
        ├── /api/dashboard
        ├── /api/cases
        ├── /api/cases/{transaction_id}
        └── /api/cases/{transaction_id}/decision (POST)
    └── static/ (Reactビルド成果物。npm run build の出力先)
```

- フロントエンド: TypeScript + React + Vite
- バックエンド: Python + FastAPI + Uvicorn（Pydanticでレスポンスモデルを定義）
- データ: すべて`backend/demo_data.py`内の固定・合成データ。DB・SQL Warehouse・外部APIには依存しない
- 状態: 調査結果の登録はメモリ内のみで保持（アプリ再起動でリセットされる想定）

---

## ディレクトリ構成

```text
/
├── app.yaml                # Databricks Apps起動定義
├── requirements.txt        # Python依存関係
├── package.json            # npm依存関係・buildスクリプト
├── tsconfig.json
├── vite.config.ts          # ビルド出力先を static/ に設定
├── index.html
├── main.py                 # FastAPIエントリポイント・static配信
├── backend/
│   ├── api.py               # APIルーター
│   ├── models.py             # Pydanticモデル
│   └── demo_data.py          # 合成データ・集計ロジック
├── src/
│   ├── main.tsx / App.tsx
│   ├── api.ts / types.ts
│   └── styles.css
├── CLAUDE.md / DEMO_SPEC.md / PHASE_PROMPTS.md
└── PLAN.md                  # Phase 0の実装計画
```

`static/` はビルド成果物のためコミット対象外です（`.gitignore`参照）。

---

## Databricks Apps上でのデプロイ方法

### 1. Databricks Appの作成

1. Databricksワークスペースの「Apps」から新規Appを作成します。
2. このリポジトリのソース一式（本README記載のファイル）をワークスペースの任意のフォルダに配置します。
3. 作成したAppのソースパスとして、上記フォルダを指定します。

### 2. デプロイ

1. Databricks Appsのデプロイ実行時、`package.json`の`build`スクリプト(`tsc && vite build`)が動作する前提です。
   ビルドステップの実行方法（自動実行か、事前ビルドが必要か）はDatabricks Appsの公式ドキュメントを参照し、
   環境に応じて調整してください。
2. `requirements.txt`に基づきPython依存関係がインストールされます。
3. `app.yaml`の`command`に従い、`uvicorn main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT}`で起動します。
4. `${DATABRICKS_APP_PORT}`の環境変数名がお使いの環境と異なる場合は、`app.yaml`を実際の変数名に合わせて修正してください。

### 3. 再デプロイ

ソースを更新した後、Databricks Apps側の「再デプロイ」操作を実行してください。ビルドから起動までの流れは初回デプロイと同じです。

### 4. 起動確認

Databricks Appsが払い出すURLへアクセスし、以下を確認します。

- `/` でアプリ画面（Phase 1時点ではAPI疎通確認画面）が表示される
- `/api/health` が `{"status":"ok",...}` を返す

---

## ローカルでの動作確認（開発時のみ）

Databricks Apps上での動作が最終確認事項ですが、開発中はローカルで下記の手順により静的整合性を確認できます。

```bash
# バックエンド
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# 別ターミナルでフロントエンドをビルド
npm install
npm run build   # static/ にビルド成果物を出力

# ブラウザで http://localhost:8000/ にアクセス
```

`npm run dev`で開発サーバーを起動する場合、`vite.config.ts`の`server.proxy`設定により`/api/*`は
`http://127.0.0.1:8000`（uvicorn）へプロキシされます。

---

## API一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/api/health` | 死活監視用 |
| GET | `/api/dashboard?scenario=rules\|hybrid&period=7d\|30d&channel=all\|mobile\|debit` | 経営ダッシュボード用のKPI・グラフ・比較・高リスク取引一覧 |
| GET | `/api/cases` | 調査ケース一覧（`status`/`priority`/`recommended_action`/`risk_band`/`q`で絞り込み可） |
| GET | `/api/cases/{transaction_id}` | 調査ケース詳細（代表ケース: `TXN-100123`） |
| POST | `/api/cases/{transaction_id}/decision` | 調査結果登録（`result`: 不正/正常/追加確認、`memo`任意） |

不正なクエリパラメータには422、存在しない取引IDには404、未処理の例外は内部情報を含まない500を返します。

---

## Phase 1 時点の実装範囲

### 実装済み

- FastAPIによる5本のAPI（正常系・主要異常系）
- 合成データ（代表ケース`TXN-100123`を含む12件の調査ケース、日次時系列によるダッシュボード集計）
- React + Vite基盤、API疎通確認ができる最小画面（ローディング/エラー/成功表示）
- Databricks Apps向けの`app.yaml`・`requirements.txt`

### 未実装（Phase 2・3で対応）

- 経営ダッシュボード(Fraud Command Center)の本格的なUI・グラフ・フィルター
- 調査ワークベンチ(Investigation Workbench)の一覧・詳細画面
- デモガイド画面

### 実装対象外（本デモの範囲外）

- データ取り込みパイプライン、Deltaテーブル、Sparkジョブ
- モデル学習・MLflow・Feature Store・Model Serving
- 外部LLM連携・RAG・チャットボット
- 実運用の自動拒否制御、実顧客データ

将来の本番構成では、これらの領域はUnity Catalogによるガバナンスや実際のモデルサービング基盤と連携する想定ですが、
本デモのコードには含まれません。

---

## 既知の制約・残課題

- Databricks Apps実機でのビルド・起動確認は未実施です（本セッションではDatabricks環境に接続できないため）。
  Phase 4でのデプロイ時に、ビルドステップの実行可否と`DATABRICKS_APP_PORT`の実際の変数名を確認してください。
- 依存関係`vite`/`esbuild`にdevサーバー限定の中程度の脆弱性が`npm audit`で報告されています（本番ビルド・配信には影響しません）。Phase 4で必要に応じてバージョン更新を検討します。
- 調査結果の登録はセッション内（プロセスメモリ）のみで保持され、アプリ再起動でリセットされます。これは仕様どおりの挙動です。
