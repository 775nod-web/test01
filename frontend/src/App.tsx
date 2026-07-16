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
  const badgeClass =
    metadata.data_mode === "databricks" ? "badge badge--databricks" : "badge badge--demo";
  return (
    <span className="header__meta">
      <span className={badgeClass}>{DATA_MODE_LABEL[metadata.data_mode] ?? metadata.data_mode}</span>
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
          const message = error instanceof Error ? error.message : "不明なエラー";
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
          const message = error instanceof Error ? error.message : "不明なエラー";
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
          const message = error instanceof Error ? error.message : "不明なエラー";
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
          const message = error instanceof Error ? error.message : "不明なエラー";
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
          const message = error instanceof Error ? error.message : "不明なエラー";
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
          <h2 className="panel__title">本日の優先顧客</h2>
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
        </section>

        <section className="panel panel--stacked" aria-label="顧客360と休眠リスク">
          <div>
            <h2 className="panel__title">顧客360</h2>
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
          </div>
          <div>
            <h2 className="panel__title">休眠リスク</h2>
            {detailState.status === "ready" && (
              <RiskPanel
                prediction={detailState.detail.prediction}
                modelMode={detailState.detail.model_mode}
              />
            )}
          </div>
        </section>

        <section className="panel" aria-label="次のアクション">
          <h2 className="panel__title">次のアクション</h2>
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
        </section>
      </main>

      <section className="feedback-section" aria-label="フィードバック概要">
        <h2 className="panel__title">フィードバック概要</h2>
        {feedbackState.status === "loading" && <p className="panel__status">読み込み中...</p>}
        {feedbackState.status === "error" && (
          <p className="panel__status panel__status--error">{feedbackState.message}</p>
        )}
        {feedbackState.status === "ready" && (
          <FeedbackSummaryPanel summary={feedbackState.summary} />
        )}
      </section>

      <footer className="footer">
        判断・施策結果を次の分析・モデル・施策改善へ戻す設計です。実際の自動再学習は本番化時に追加します。
      </footer>
    </div>
  );
}
