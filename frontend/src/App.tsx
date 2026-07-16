import { useEffect, useState } from "react";
import "./App.css";
import {
  fetchCustomerDetail,
  fetchCustomers,
  fetchFeedbackSummary,
  fetchHealth,
  fetchMetadata,
  fetchRecommendation,
} from "./api/client";
import { CustomerListPanel } from "./components/CustomerListPanel";
import { Customer360Panel } from "./components/Customer360Panel";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { FeedbackSummaryPanel } from "./components/FeedbackSummaryPanel";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { RiskPanel } from "./components/RiskPanel";
import type {
  CustomerDetailResponse,
  CustomerSummary,
  FeedbackSummaryResponse,
  MetadataResponse,
  RecommendationResponse,
} from "./types";

type HeaderState =
  | { status: "loading" }
  | { status: "ready"; metadata: MetadataResponse }
  | { status: "error"; message: string };

type CustomerListState =
  | { status: "loading" }
  | { status: "ready"; customers: CustomerSummary[] }
  | { status: "error"; message: string };

type CustomerDetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; detail: CustomerDetailResponse }
  | { status: "error"; message: string };

type RecommendationState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; recommendation: RecommendationResponse }
  | { status: "error"; message: string };

type FeedbackSummaryState =
  | { status: "loading" }
  | { status: "ready"; summary: FeedbackSummaryResponse }
  | { status: "error"; message: string };

const DATA_MODE_LABEL: Record<string, string> = {
  demo: "合成データ（demo）",
  databricks: "Databricks接続",
};

const MODEL_MODE_LABEL: Record<string, string> = {
  trained: "実学習モデル",
  precomputed: "事前計算済み予測",
};

function formatUpdatedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ja-JP");
  } catch {
    return iso;
  }
}

function HeaderMeta({ state }: { state: HeaderState }) {
  if (state.status === "loading") {
    return <span className="header__meta">読み込み中...</span>;
  }
  if (state.status === "error") {
    return (
      <span className="header__meta">
        <span className="badge badge--error">API未接続</span>
        {state.message}
      </span>
    );
  }
  const { metadata } = state;
  const dataModeBadgeClass =
    metadata.data_mode === "databricks" ? "badge badge--databricks" : "badge badge--demo";
  return (
    <span className="header__meta">
      <span className={dataModeBadgeClass}>
        {DATA_MODE_LABEL[metadata.data_mode] ?? metadata.data_mode}
      </span>
      {metadata.model_mode && (
        <span className="badge badge--model-mode">
          {MODEL_MODE_LABEL[metadata.model_mode] ?? metadata.model_mode}
        </span>
      )}
      <span>最終更新: {formatUpdatedAt(metadata.updated_at)}</span>
    </span>
  );
}

export default function App() {
  const [headerState, setHeaderState] = useState<HeaderState>({ status: "loading" });
  const [listState, setListState] = useState<CustomerListState>({ status: "loading" });
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [detailState, setDetailState] = useState<CustomerDetailState>({ status: "idle" });
  const [recommendationState, setRecommendationState] = useState<RecommendationState>({
    status: "idle",
  });
  const [feedbackState, setFeedbackState] = useState<FeedbackSummaryState>({ status: "loading" });
  const [feedbackRefreshKey, setFeedbackRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await fetchHealth();
        const metadata = await fetchMetadata();
        if (!cancelled) {
          setHeaderState({ status: "ready", metadata });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラーが発生しました。";
          setHeaderState({ status: "error", message });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetchCustomers();
        if (cancelled) {
          return;
        }
        setListState({ status: "ready", customers: response.customers });
        if (response.customers.length > 0) {
          setSelectedCustomerId(response.customers[0].customer_id);
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラーが発生しました。";
          setListState({ status: "error", message });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedCustomerId) {
      return;
    }
    let cancelled = false;
    setDetailState({ status: "loading" });
    setRecommendationState({ status: "loading" });

    async function loadDetail() {
      try {
        const detail = await fetchCustomerDetail(selectedCustomerId!);
        if (!cancelled) {
          setDetailState({ status: "ready", detail });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラーが発生しました。";
          setDetailState({ status: "error", message });
        }
      }
    }

    async function loadRecommendation() {
      try {
        const recommendation = await fetchRecommendation(selectedCustomerId!);
        if (!cancelled) {
          setRecommendationState({ status: "ready", recommendation });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラーが発生しました。";
          setRecommendationState({ status: "error", message });
        }
      }
    }

    void loadDetail();
    void loadRecommendation();
    return () => {
      cancelled = true;
    };
  }, [selectedCustomerId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const summary = await fetchFeedbackSummary();
        if (!cancelled) {
          setFeedbackState({ status: "ready", summary });
        }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "不明なエラーが発生しました。";
          setFeedbackState({ status: "error", message });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [feedbackRefreshKey]);

  return (
    <div className="app">
      <header className="header">
        <h1 className="header__title">顧客休眠予兆・次アクション支援デモ</h1>
        <HeaderMeta state={headerState} />
      </header>

      <main className="layout">
        <section className="panel" aria-label="本日の優先顧客">
          <h2 className="panel__title">① 本日の優先顧客</h2>
          <ErrorBoundary label="本日の優先顧客">
            {listState.status === "loading" && <p className="panel__status">読み込み中...</p>}
            {listState.status === "error" && (
              <p className="panel__status panel__status--error">{listState.message}</p>
            )}
            {listState.status === "ready" && (
              <CustomerListPanel
                customers={listState.customers}
                selectedCustomerId={selectedCustomerId}
                onSelect={setSelectedCustomerId}
              />
            )}
          </ErrorBoundary>
        </section>

        <section className="panel panel--stacked" aria-label="顧客360と休眠リスク">
          <div>
            <h2 className="panel__title">② 顧客360</h2>
            <ErrorBoundary label="顧客360">
              {detailState.status === "idle" && (
                <p className="panel__status">左の一覧から顧客を選択してください。</p>
              )}
              {detailState.status === "loading" && <p className="panel__status">読み込み中...</p>}
              {detailState.status === "error" && (
                <p className="panel__status panel__status--error">{detailState.message}</p>
              )}
              {detailState.status === "ready" && (
                <Customer360Panel customer={detailState.detail.customer} />
              )}
            </ErrorBoundary>
          </div>
          <div>
            <h2 className="panel__title">③ 休眠リスク</h2>
            <ErrorBoundary label="休眠リスク">
              {detailState.status === "ready" && (
                <RiskPanel
                  prediction={detailState.detail.prediction}
                  modelMode={detailState.detail.model_mode}
                />
              )}
            </ErrorBoundary>
          </div>
        </section>

        <section className="panel" aria-label="次のアクション">
          <h2 className="panel__title">④ 次のアクション</h2>
          <ErrorBoundary label="次のアクション">
            {recommendationState.status === "idle" && (
              <p className="panel__status">左の一覧から顧客を選択してください。</p>
            )}
            {recommendationState.status === "loading" && (
              <p className="panel__status">読み込み中...</p>
            )}
            {recommendationState.status === "error" && (
              <p className="panel__status panel__status--error">{recommendationState.message}</p>
            )}
            {recommendationState.status === "ready" && selectedCustomerId && (
              <RecommendationPanel
                key={selectedCustomerId}
                customerId={selectedCustomerId}
                recommendation={recommendationState.recommendation}
                onDecisionSaved={() => setFeedbackRefreshKey((key) => key + 1)}
              />
            )}
          </ErrorBoundary>
        </section>
      </main>

      <section className="feedback-section" aria-label="フィードバック概要">
        <h2 className="panel__title">⑥ フィードバック概要</h2>
        <ErrorBoundary label="フィードバック概要">
          {feedbackState.status === "loading" && <p className="panel__status">読み込み中...</p>}
          {feedbackState.status === "error" && (
            <p className="panel__status panel__status--error">{feedbackState.message}</p>
          )}
          {feedbackState.status === "ready" && (
            <FeedbackSummaryPanel summary={feedbackState.summary} />
          )}
        </ErrorBoundary>
      </section>

      <details className="demo-info">
        <summary>デモ構成／本番化時に追加する事項</summary>
        <div className="demo-info__body">
          <div>
            <h3>デモで実装済み</h3>
            <ul>
              <li>複数サービスの合成データ統合（EC・QR決済・カード・ネット銀行・過去施策・問い合わせ）</li>
              <li>customer_idで統合した顧客360</li>
              <li>ベースラインの休眠予測（単純で説明可能な分類モデル）</li>
              <li>実LLMを主経路とし、事前生成済み回答・ルールベース生成をフォールバックに持つ根拠付きアクション候補</li>
              <li>人間による承認・修正・見送りの判断</li>
              <li>判断のフィードバック記録</li>
            </ul>
          </div>
          <div>
            <h3>本番化時に追加</h3>
            <ul>
              <li>実際の業務システム・Databricks SQL/Unity Catalogへの接続</li>
              <li>サービス間の高度なID解決・PIIマスキング・行列レベルアクセス制御</li>
              <li>モデルの継続的な監視・自動再学習</li>
              <li>外部施策配信システムとの本番連携（本デモは自動配信を行わない）</li>
              <li>Databricks側の判断保存先（Delta テーブル等）への接続</li>
            </ul>
          </div>
        </div>
      </details>

      <footer className="footer">
        判断・施策結果を次の分析・モデル・施策改善へ戻す設計です。実際の自動再学習は本番化時に追加します。
      </footer>
    </div>
  );
}
