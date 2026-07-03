# Phase 2: Frontend UI プロンプト

`serving_layer/CLAUDE.md` と Phase 1 で実装した API 契約（`app/backend/models.py` のレスポンス形状）を前提に、以下を実施してください。

## ゴール

TypeScript + React（Vite、Streamlit は使用しない）で、Gold layer の4つのビジネス目的にそれぞれ対応する4画面を持つ SPA を `serving_layer/app/frontend/` に実装してください。

## 共通要件

- ルーティングは `react-router-dom`。左サイドバーに4つのメニュー（経営KPI／プラン別売上／要フォローアップ顧客／データ品質）を常時表示。
- カラーは `src/theme/colors.ts` に定義する。UIチャンパー（サイドバー、カード背景、バッジ）には Google スライド風の淡く鮮やかなパステルカラーを使う。グラフの系列色はアクセシビリティ検証済みの配色を使い、パステルと使い分けること（詳細は CLAUDE.md 参照）。
- グラフは `recharts` を使用し、1チャートにつき1つのY軸（2軸グラフを作らない）。
- ローディング・エラー状態を必ず表示する（無言で真っ白にしない）。
- レスポンシブ（最低でもラップトップ〜デスクトップ幅で崩れない）。

## 画面ごとの要件

### 1. 経営KPIダッシュボード（`pages/DailyKpiDashboard.tsx`）— 対象: 経営層
- 期間セレクタ（直近7/30/90日）。
- 当日（期間末日）のサマリーカード: DAU、有料ユーザー数、当日売上、無料→有料転換率。
- 時系列グラフ: 売上推移、DAU推移、新規登録数と解約数の比較。
- `upgrade_click_count` と `cancel_click_count` を並べて「転換意向 vs 解約意向」を可視化し、経営層が意思決定しやすいようにする。

### 2. プラン別売上（`pages/SalesPerPlan.tsx`）— 対象: 事業企画・プロダクト
- 月次×プランの売上推移（積み上げ棒 or 折れ線、プランごとに固定の系列色）。
- プラン別の `failed_payment_rate` を強調表示し、失敗率が高い（収益停滞の疑いがある）プランを一目で分かるようにする。
- テーブルビュー（`avg_transaction_amount`, `active_subscriber_count`, `churned_subscriber_count` を含む）。

### 3. 要フォローアップ顧客（`pages/FailedPaymentUsers.tsx`）— 対象: CS・営業
- `churn_risk_flag` でフィルタ可能なテーブル。解約リスクは色付きバッジ（status palette）で表現し、色だけに依存せずラベルも併記する。
- `user_segment` / `plan_type` / `country_code` での絞り込み。
- `total_failed_count` 降順がデフォルト。CSVエクスポート等は不要（範囲外）。

### 4. データ品質サマリー（`pages/DataQualitySummary.tsx`）— 対象: データエンジニアリング
- `run_date` × `source_table` × `dq_check_name` のヒートマップまたは一覧テーブル。
- 直近の日付で問題が集中している source_table / check を目立たせる。

## API 呼び出し

- `src/api/client.ts` に fetch ラッパーを実装し、ベースURLは相対パス（`/api/v1/...`）とする（Databricks Apps では同一オリジンで配信されるため）。
- ローカル開発時は Vite の `server.proxy` で `http://localhost:8000` にプロキシする設定を `vite.config.ts` に入れる。

## 確認事項

- `npm run build` が通ること。
- 主要4画面をブラウザで開き、モックまたは実データでレンダリング崩れがないことを確認する（`/verify` skill 相当のチェックを行う）。
