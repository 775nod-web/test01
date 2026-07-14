# PLAN.md — Phase 0: 現状確認と実装計画

本ドキュメントは `CLAUDE.md` と `DEMO_SPEC.md` を最上位ルールとして、Databricks Apps上で
稼働する「Fraud Decision Center」デモの実装計画を示す。このフェーズではコード実装は行わない。

---

## 1. リポジトリ現状調査

### 既存ファイル

```text
/
├── generate_ecommerce_sample_data.py   # PySpark: ECサイト合成データ生成（ノートブック用）
├── save_bronze_delta_tables.py         # PySpark: Deltaテーブル(Bronze層)保存（ノートブック用）
├── CLAUDE.md                            # 今回配置
├── DEMO_SPEC.md                         # 今回配置
├── PHASE_PROMPTS.md                     # 今回配置
└── .claude/settings.local.json          # Claude Code権限設定（対象外）
```

- アプリの土台（`package.json` / `requirements.txt` / `app.yaml` / `src/` / `backend/` 等）は存在しない。ゼロから構築する。
- `generate_ecommerce_sample_data.py` と `save_bronze_delta_tables.py` は、今回の不正対策デモとは無関係な別タスク（ECサイトの合成データ生成・Delta Bronze層保存）の成果物であり、別ブランチ `claude/ecommerce-pyspark-sample-data-7d1j50` にも同名の作業が存在する。
- ローカル環境には Node.js v22 / npm v10 / Python 3.11 が利用可能であり、ビルドとPythonの静的確認は本セッションで実行できる（Databricks Apps上での実起動確認はPhase 4で別途必要）。

### CLAUDE.mdとの整合性確認

- この2ファイルはSparkジョブの実装・Deltaテーブル作成という、CLAUDE.md 第9章「禁止事項」に明記された行為そのものである。
- ただし、これらは**今回作成するアプリのビルドや実行経路には含まれない**（`requirements.txt`・`package.json`・`main.py` のいずれからも参照しない）ため、実装対象と物理的に衝突はしない。
- 一方でリポジトリ内に禁止事項に該当するコードが残る状態は、CLAUDE.mdの「対象範囲は後述の2画面とその操作だけに限定する」という条件と趣旨的にそぐわない。
- **本フェーズでは削除・変更を行わない**（無関係な既存ファイルを推測で削除する方が危険なため）。取り扱い方針（残す/削除する/別ディレクトリへ退避する）はユーザー判断を仰ぐ、Phase 0終了時の未解決事項として報告する。

---

## 2. 採用アーキテクチャ

```text
Databricks Apps (1 App / 1 Pythonプロセス)
└── uvicorn main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT}
    └── FastAPI (backend/)
        ├── /api/health, /api/dashboard, /api/cases, /api/cases/{id}, /api/cases/{id}/decision
        └── StaticFiles マウント: static/ (Reactビルド成果物, ビルド時に生成)
```

- ビルド時（Databricks Appsのデプロイ時）に `npm run build` を実行し、Viteの出力を `static/` に生成する。
- 実行時はFastAPI 1プロセスのみが起動し、APIと静的ファイルを同一オリジンで配信する。CORS設定は不要。
- 状態はすべてPythonプロセスのメモリ上（`backend/demo_data.py` 内のインメモリ構造）に保持し、再起動で消えることを許容する。
- SQL Warehouse・Model Serving・Lakebase・Unity Catalog・外部APIへの依存は一切持たない。

---

## 3. 依存関係（最小構成）

### Python（`requirements.txt`）

```text
fastapi
uvicorn[standard]
pydantic
```

以上3つのみ。DB接続、ORM、認証ライブラリは追加しない。

### フロントエンド（`package.json` の主要依存）

```text
dependencies:
  react
  react-dom
  react-router-dom      # 概況/調査ケース/デモガイドの画面遷移用
  recharts               # 軽量チャートライブラリ（Phase 2で採用、1種類のみ）

devDependencies:
  typescript
  vite
  @vitejs/plugin-react
  @types/react
  @types/react-dom
```

- チャートライブラリは `recharts` の1つに固定する（CLAUDE.md「軽量なチャートライブラリを避ける」「1つだけ使用」要件に対応）。他候補（visx, nivo, chart.js）より依存サイズが小さく、Reactとの親和性が高いため採用。
- 状態管理ライブラリ（Redux等）は導入しない。React標準の `useState`/`useContext` で画面間の最小限の共有状態（シナリオ・期間・チャネル選択、セッション内の調査結果）を扱う。
- Node.jsはビルド専用。バックエンドには使用しない。

---

## 4. ファイル構成設計

```text
/
├── app.yaml                     # Databricks Apps起動定義
├── requirements.txt             # Python依存関係（3行のみ）
├── package.json                 # npm依存関係・buildスクリプト
├── package-lock.json            # npm ci用ロックファイル
├── tsconfig.json                # TypeScript設定
├── vite.config.ts               # ビルド出力先を static/ に設定
├── index.html                   # Viteエントリ
├── main.py                      # FastAPIアプリ生成・static/マウント
├── backend/
│   ├── __init__.py
│   ├── api.py                   # APIルーター（/api/*）
│   ├── models.py                # Pydanticレスポンス/リクエストモデル
│   └── demo_data.py             # 固定合成データ + インメモリ状態（rules/hybrid, 7d/30d, channel別）
├── src/
│   ├── main.tsx                 # Reactエントリ
│   ├── App.tsx                  # ルーティング（概況/調査ケース/デモガイド）
│   ├── api.ts                   # fetchラッパー
│   ├── types.ts                 # API型定義（バックエンドPydanticと対応）
│   ├── styles.css                # 共通スタイル（Googleライクな配色トークン）
│   ├── components/
│   │   ├── layout/               # グローバルナビ、合成データ注記バナー
│   │   ├── dashboard/            # KPIカード、比較カード、チャート、高リスク一覧
│   │   └── workbench/            # ケース一覧テーブル、詳細セクション群、判定登録フォーム
│   └── pages/
│       ├── DashboardPage.tsx     # Fraud Command Center
│       ├── WorkbenchPage.tsx     # Investigation Workbench（一覧+詳細）
│       └── GuidePage.tsx         # デモガイド
├── PLAN.md                       # 本ファイル
├── CLAUDE.md
├── DEMO_SPEC.md
├── PHASE_PROMPTS.md
└── README.md                     # Phase 1で初版作成、Phase 4で最終化
```

`static/` はビルド生成物のため、`.gitignore` に追加しコミット対象外とする（Databricks Apps側のビルドステップで生成させる想定。ビルドステップが利用できない場合はPhase 4でコミット済み成果物を配置する代替案を検討する）。

---

## 5. Databricks Appsのビルド・起動フロー

1. Databricks Apps側でこのリポジトリ（またはワークスペースにデプロイされたソース）を指定してAppを作成する。
2. デプロイ実行時、`package.json` の `build` スクリプト（`vite build`、出力先 `static/`）でReactをビルドする。
3. `requirements.txt` を用いてPython依存をインストールする。
4. `app.yaml` の `command` に従い、`uvicorn main:app --host 0.0.0.0 --port ${DATABRICKS_APP_PORT}` でプロセスを起動する。
5. FastAPI起動時に `static/` の存在を確認し、`StaticFiles` としてマウント、`/` 配下でReactのSPAを配信、`/api/*` はAPIルーターへ委譲する。
6. Databricks Apps側の正確なビルドコマンド指定方法・環境変数名（`DATABRICKS_APP_PORT` か別名か）はPhase 4のデプロイ時に公式ドキュメント/実環境で確認し、必要なら`app.yaml`を調整する。

---

## 6. 各フェーズの検証方法

| フェーズ | 検証内容 | 方法 |
|---|---|---|
| Phase 1 | Python構文・型/APIの正常系・異常系/Reactビルド成否 | `python -m py_compile`、`uvicorn`起動+`curl`でAPI疎通、`npm run build`、可能なら`pytest` |
| Phase 2 | ダッシュボードの表示・フィルター連動・コンソールエラー | `npm run build`成功確認、`tsc --noEmit`、ローカルでuvicorn起動しAPI応答をブラウザ相当で確認（本番同等の起動確認はPhase 4） |
| Phase 3 | ケース一覧→詳細遷移、調査結果登録の状態反映、デモガイド表示 | 同上 + POST `/api/cases/{id}/decision` のレスポンスとGET再取得での反映確認 |
| Phase 4 | Databricks Apps実環境での起動・API疎通・静的配信 | Databricks Appsへのデプロイ、実URLでの動作確認、ログ確認 |

各フェーズとも「ローカルでのビルド・静的検証」までがこのセッションで可能な範囲であり、「Databricks Apps上での実起動確認」はPhase 4でのみ確定させる。

---

## 7. リスクと回避策

| リスク | 回避策 |
|---|---|
| Databricks Appsの環境変数名がドキュメントと異なる可能性 | `app.yaml`はCLAUDE.md記載の`DATABRICKS_APP_PORT`を基本形とし、Phase 4のデプロイ時に実際のログ/公式ドキュメントで確認し必要なら修正する |
| `static/`ビルド成果物をコミットするかどうかの判断 | Databricks Appsのビルドステップで`npm run build`が実行される前提を基本とし、Phase 4で実行できないと判明した場合はビルド成果物を明示的にコミットする代替手順に切り替える |
| npmが利用できないDatabricks環境である可能性 | PHASE_PROMPTS.mdの指示通り、Node.js非依存でも「コードと設定の静的整合性」を確認できるようにし、Phase 4で実際のビルド可否を確認して記録する |
| 既存の無関係ファイル（Delta/Sparkスクリプト）が禁止事項と紛らわしい | 削除せず現状維持。取り扱い方針をユーザーに確認する（本セクション末尾の未解決事項） |
| 合成データの数値が画面間・シナリオ間で矛盾する | `backend/demo_data.py`に単一の真実源（single source of truth）を置き、全APIがそこから導出する設計にする（Phase 1で実装） |
| チャートライブラリが軽量要件を満たさない/描画が重い | `recharts`採用、データ点数を小さく保つ（日別30日分程度）、不要なアニメーションを避ける |

---

## 8. Phase 0 終了報告

### 調査したファイル
- `generate_ecommerce_sample_data.py`
- `save_bronze_delta_tables.py`
- `.claude/settings.local.json`
- リポジトリのブランチ構成（`git branch -a`）

### 作成・更新したファイル
- `CLAUDE.md`（新規配置）
- `DEMO_SPEC.md`（新規配置）
- `PHASE_PROMPTS.md`（新規配置）
- `PLAN.md`（新規作成、本ファイル）

### 採用アーキテクチャ
- 1 Databricks App / 1 FastAPIプロセス、Reactは静的ビルドしてFastAPIから同一オリジン配信。詳細は本ドキュメント第2〜4章。

### Databricks Appsデプロイまでの手順（概要）
第5章参照。Phase 1〜3でアプリ本体を実装し、Phase 4で実デプロイと動作確認を行う。

### 次フェーズ（Phase 1）の作業範囲
- アプリ基盤（`app.yaml`, `requirements.txt`, `package.json`, `vite.config.ts`, `main.py`）の作成
- `backend/`（API・モデル・合成データ）の実装
- 5本のAPIエンドポイントの実装と正常系・異常系確認
- API疎通確認用の最小React画面
- README.md初版作成

### 未解決事項（ユーザー判断が必要）
1. **既存の無関係ファイルの扱い**: `generate_ecommerce_sample_data.py` と `save_bronze_delta_tables.py` は今回のデモ対象外（別タスクの成果物）。このまま残す／削除する／別ブランチに委ねるのいずれを希望するか確認したい。今回のアプリの実行には影響しないため、指示があるまで変更しない。
2. **Databricks Appsのビルドステップの前提**: 本セッションではDatabricks Apps実機に接続できないため、「デプロイ時に`npm run build`が自動実行される」という前提の正確性はPhase 4で検証が必要。
3. **リポジトリ内でのDatabricks Appsデプロイ設定**（Appの新規作成か既存App更新か、ワークスペースパスなど）はユーザー側の環境情報が必要になるため、Phase 4開始前に確認する。

Phase 0はここまでとし、機能実装は行っていない。Phase 1のプロンプトを受け取り次第、上記計画に沿って着手する。
