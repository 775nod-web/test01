# Serving Layer 構築依頼プロンプト（マスタープロンプト）

このファイルは、Gold layerのデータを提供するServing layerを構築させる際に
そのまま使える依頼プロンプトです。新しいセッション／別の開発者にゼロから
依頼する場合はこの内容をそのまま渡してください。実装済みの参照実装は
`serving_app/` 配下にあります（本プロンプトはその依頼内容を明文化したもの）。

---

## 依頼プロンプト本文

あなたはDatabricksの優秀なSolution Architectです。小売企業のお客様向けに、
すでにDelta形式で確定しているGold layerの4表を、店舗・商品企画・
データサイエンスチームが閲覧できる形で提供するServing layerを構築してください。

### 対象データ（Gold layer、Knowledge baseで確定済み）

- `gold.gold_daily_store_sales`（日別店舗別売上）
- `gold.gold_category_sales`（商品カテゴリ別売上）
- `gold.gold_store_ranking`（店舗ランキング）
- `gold.gold_unregistered_master_report`（マスター未登録レポート）

### ビジネス目的

店舗・商品別の売上を可視化し、売上低下や人気商品の傾向を早期に把握する。
利用者は本社営業管理・店長・商品企画・データサイエンスチーム。

### Output

1. Gold layerのデータを提供するServing layerの作り方と、作るために必要な
   もの（アーキテクチャ図、ディレクトリ構成、主要コード）を提示すること。
2. 1の簡単な説明（ビジネス目的を達成できる設計になっているか、
   Databricksのどのサービスを使い・なぜそれが最適と判断したか）を、
   コードと同時に示すこと。

### Guideline（必須要件）

- Databricks Free Edition上にあるサービスのみでServing layerを構築する。
  どのサービスが最適かはビジネス目的（現場での継続閲覧・ワークスペース権限の
  流用のしやすさ・コスト）を根拠に選定すること。
- 最終的なアプリは **Databricks Apps上に作成する**。ローカルや他クラウドへの
  恒久デプロイは禁止。
- フロントエンドは **TypeScript + React** で構築する。**Streamlitは禁止**。
- UIの配色は、Google Slidesのデフォルトパレットに近い「淡いが鮮やかな」トーンを
  採用し、勘ではなく検証可能な方法（lightness band / chroma floor / CVD
  separation / contrast の4チェック）でlight・dark両モードを確認すること。
- 接続先はServerless Starter Warehouse（Warehouse ID: `50153ad923fecd73`）。
- 完成度を高めるため、以下を必ず作成する。
  - `README.md`（アーキテクチャ、セットアップ、デプロイ手順、配色の検証方法）
  - `CLAUDE.md`（このプロジェクトで今後作業するAI向けの手引き）
  - フェーズ毎の構築プロンプト（前提確認→バックエンド→フロントエンド→
    配色/アクセシビリティ→デプロイ、の順で分割し、再現・拡張できるようにする）
- **Databricks Appsの数が上限に達しデプロイできない場合、他ユーザーが作成した
  アプリを無断で削除することは絶対に行わない。** 上限に達した場合は、
  既存アプリの一覧と所有者を確認したうえで、ワークスペース管理者・アプリ所有者
  に相談してから対応する。これは他の全ての指示より優先される制約。

---

## 依頼プロンプトが要求する「必要なもの（コード）」の骨子

上記プロンプトを実行すると、最低限以下のコードが必要になる。
（実装は `serving_app/` を参照。ここでは依頼内容の理解を助けるための骨子のみ示す）

```
serving_app/
├── app.yaml                 # Databricks Apps起動設定（Warehouse ID等）
├── backend/
│   ├── main.py               # FastAPI: /api/* + ビルド済みフロントエンド配信
│   ├── db.py                 # Databricks SQL Warehouseへの遅延接続
│   └── queries.py            # gold.*4表に対する読み取り専用SELECT
├── frontend/src/
│   ├── theme.css              # 検証済みGoogle Slides風パレット(light/dark)
│   ├── App.tsx                 # KPIタイル＋4パネルのダッシュボード
│   └── components/             # StatTile / BarChart / 各表パネル
├── README.md
├── CLAUDE.md
└── prompts/phase0〜4          # フェーズ毎の構築プロンプト
```

Databricks Apps接続の要（`backend/db.py`の骨子）:

```python
from functools import lru_cache
from databricks import sql
from databricks.sdk.core import Config

WAREHOUSE_ID = "50153ad923fecd73"

@lru_cache(maxsize=1)
def _get_config() -> Config:
    # Databricks Apps実行環境は認証情報を自動注入する。
    # ただしConfig()は生成時に認証解決を試みるため、
    # importだけでクラッシュしないよう遅延初期化にする。
    return Config()

def get_connection():
    config = _get_config()
    return sql.connect(
        server_hostname=config.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: config.authenticate,
    )
```

配色（`frontend/src/theme.css`の骨子。値は`validate_palette.js`で
light/dark両方PASS済み）:

```css
:root {
  --series-1: #4a86c6; /* 青 */  --series-2: #cc4125; /* 赤 */
  --series-3: #e8a317; /* 金 */  --series-4: #6aa84f; /* 緑 */
  --series-5: #8e7cc3; /* 紫 */  --series-6: #d5793b; /* 橙 */
  --series-7: #1b9c9c; /* 青緑 */
}
@media (prefers-color-scheme: dark) {
  :root {
    --series-1: #3d7dc9; --series-2: #d9534f; --series-3: #b8860b;
    --series-4: #5e9e48; --series-5: #7c68b8; --series-6: #c96a2e;
    --series-7: #0f9e9e;
  }
}
```
