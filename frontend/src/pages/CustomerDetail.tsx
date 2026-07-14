import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { HumanReviewBadge, RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { ErrorState, LoadingState } from "../components/States";
import { TrendChart } from "../components/TrendChart";
import { BUSINESS_QUESTIONS, COMMON, PAGE_TITLES, t } from "../i18n/ja";
import type { CustomerDetailResponse } from "../types";

function pct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(0)}%`;
}

function money(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function CustomerDetail() {
  const { customerId = "" } = useParams();
  const [data, setData] = useState<CustomerDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setData(null);
    setError(null);
    setNotFound(false);
    api
      .customerDetail(customerId)
      .then(setData)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setError(e instanceof ApiError ? e.message : "この顧客データを読み込めませんでした。");
        }
      });
  }, [customerId]);

  if (notFound) {
    return (
      <div>
        <PageHeader title={PAGE_TITLES.customer360} question={BUSINESS_QUESTIONS.customer360} />
        <div className="card">
          <p>顧客ID「{customerId}」は見つかりませんでした。</p>
          <Link to="/segments" className="btn">
            顧客セグメント分析に戻る
          </Link>
        </div>
      </div>
    );
  }
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="顧客データを読み込み中…" />;

  return (
    <div>
      <PageHeader title={`顧客360 — ${data.customer_id}`} question={BUSINESS_QUESTIONS.customer360} />

      <div className="card">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <RiskBadge segment={data.risk_segment} />
          <ValueBadge segment={data.value_segment} />
          <HumanReviewBadge required={data.human_review_required} />
        </div>
        <div className="grid grid--kpis">
          <div>
            <p className="section-subtitle">契約期間</p>
            <p className="section-title">{data.tenure_months} か月</p>
          </div>
          <div>
            <p className="section-subtitle">現在の残高</p>
            <p className="section-title">{money(data.current_balance)}</p>
          </div>
          <div>
            <p className="section-subtitle">シミュレーション年間価値</p>
            <p className="section-title">{money(data.simulated_annual_value)}</p>
          </div>
          <div>
            <p className="section-subtitle">推定価値リスク</p>
            <p className="section-title">
              {money(data.estimated_value_at_risk)}（{COMMON.simulated}）
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid--2col">
        <div className="card">
          <p className="section-title">
            リスクスコア：{data.risk_score_normalized_100} / 100
          </p>
          <p className="section-subtitle">
            透明性のあるポイントスコア（内部値 {data.risk_score} / 129）— 予測モデルではありません。
          </p>
          <div className="table-scroll">
            <table className="data-table">
              <tbody>
                <tr>
                  <th scope="row">リスク区分</th>
                  <td>{t.riskSegment(data.risk_segment)}</td>
                </tr>
                <tr>
                  <th scope="row">検知シグナル</th>
                  <td>{data.triggered_signal_count} / 8</td>
                </tr>
                <tr>
                  <th scope="row">主なリスク要因</th>
                  <td>{t.driver(data.primary_driver)}</td>
                </tr>
                <tr>
                  <th scope="row">副次的なリスク要因</th>
                  <td>{t.driver(data.secondary_driver)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <p className="section-title">推奨アクション</p>
          <p className="section-subtitle">意思決定支援 — 連絡前に必ず担当者による確認が必要です。</p>
          <div className="table-scroll">
            <table className="data-table">
              <tbody>
                <tr>
                  <th scope="row">アクション</th>
                  <td>{t.action(data.recommended_action)}</td>
                </tr>
                <tr>
                  <th scope="row">チャネル</th>
                  <td>{t.channel(data.recommended_channel)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card">
        <p className="section-title">残高推移</p>
        <p className="section-subtitle">
          90日変化: {pct(data.balance_change_90d_pct)} ・ 30日変化: {pct(data.balance_change_30d_pct)}
        </p>
        <TrendChart
          data={data.trends.map((tr) => ({ month: tr.activity_month, value: tr.eom_balance }))}
          color="#4285F4"
          formatValue={money}
        />
      </div>

      <div className="grid grid--2col">
        <div className="card">
          <p className="section-title">カード利用推移</p>
          <p className="section-subtitle">90日変化: {pct(data.card_spend_change_90d_pct)}</p>
          <TrendChart
            data={data.trends.map((tr) => ({ month: tr.activity_month, value: tr.card_spend_amount }))}
            color="#EA4335"
            formatValue={money}
          />
        </div>
        <div className="card">
          <p className="section-title">アプリ利用推移</p>
          <p className="section-subtitle">
            90日変化: {pct(data.login_change_90d_pct)} ・ 前回ログインから {data.days_since_last_login} 日
          </p>
          <TrendChart
            data={data.trends.map((tr) => ({ month: tr.activity_month, value: tr.login_count }))}
            color="#34A853"
            formatValue={(v) => `${v} 回ログイン`}
          />
        </div>
      </div>

      <div className="card">
        <p className="section-title">問い合わせ・苦情履歴</p>
        {data.contact_history.length === 0 ? (
          <p className="section-subtitle">履歴はありません。</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">日付</th>
                  <th scope="col">チャネル</th>
                  <th scope="col">理由</th>
                  <th scope="col">苦情</th>
                  <th scope="col">解決済み</th>
                  <th scope="col">満足度</th>
                </tr>
              </thead>
              <tbody>
                {data.contact_history.map((c, i) => (
                  <tr key={i}>
                    <td>{c.contact_date}</td>
                    <td>{t.contactChannel(c.channel)}</td>
                    <td>{t.contactReason(c.reason)}</td>
                    <td>{c.is_complaint ? COMMON.yes : COMMON.no}</td>
                    <td>{c.is_resolved ? COMMON.yes : COMMON.no}</td>
                    <td>{c.satisfaction_score} / 5</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
