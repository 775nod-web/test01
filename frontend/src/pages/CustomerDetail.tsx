import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { HumanReviewBadge, RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { ErrorState, LoadingState } from "../components/States";
import { TrendChart } from "../components/TrendChart";
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
          setError(e instanceof ApiError ? e.message : "Unable to load this customer.");
        }
      });
  }, [customerId]);

  if (notFound) {
    return (
      <div>
        <PageHeader title="Customer 360" question="Why should this customer be prioritized, and how should we respond?" />
        <div className="card">
          <p>No customer found with ID "{customerId}".</p>
          <Link to="/segments" className="btn">
            Back to Segment Explorer
          </Link>
        </div>
      </div>
    );
  }
  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading customer…" />;

  return (
    <div>
      <PageHeader title={`Customer 360 — ${data.customer_id}`} question="Why should this customer be prioritized, and how should we respond?" />

      <div className="card">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <RiskBadge segment={data.risk_segment} />
          <ValueBadge segment={data.value_segment} />
          <HumanReviewBadge required={data.human_review_required} />
        </div>
        <div className="grid grid--kpis">
          <div>
            <p className="section-subtitle">Tenure</p>
            <p className="section-title">{data.tenure_months} months</p>
          </div>
          <div>
            <p className="section-subtitle">Current balance</p>
            <p className="section-title">{money(data.current_balance)}</p>
          </div>
          <div>
            <p className="section-subtitle">Simulated annual value</p>
            <p className="section-title">{money(data.simulated_annual_value)}</p>
          </div>
          <div>
            <p className="section-subtitle">Estimated value at risk</p>
            <p className="section-title">{money(data.estimated_value_at_risk)} (simulated)</p>
          </div>
        </div>
      </div>

      <div className="grid grid--2col">
        <div className="card">
          <p className="section-title">Risk score: {data.risk_score} / 129</p>
          <p className="section-subtitle">Transparent point score — not a predictive model.</p>
          <table className="data-table">
            <tbody>
              <tr>
                <th scope="row">Primary driver</th>
                <td>{data.primary_driver}</td>
              </tr>
              <tr>
                <th scope="row">Secondary driver</th>
                <td>{data.secondary_driver}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="card">
          <p className="section-title">Recommended action</p>
          <p className="section-subtitle">Decision support — requires human review before contact.</p>
          <table className="data-table">
            <tbody>
              <tr>
                <th scope="row">Action</th>
                <td>{data.recommended_action}</td>
              </tr>
              <tr>
                <th scope="row">Channel</th>
                <td>{data.recommended_channel}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <p className="section-title">Balance trend</p>
        <p className="section-subtitle">
          90-day change: {pct(data.balance_change_90d_pct)} · 30-day change: {pct(data.balance_change_30d_pct)}
        </p>
        <TrendChart
          data={data.trends.map((t) => ({ month: t.activity_month, value: t.eom_balance }))}
          color="#4285F4"
          formatValue={money}
        />
      </div>

      <div className="grid grid--2col">
        <div className="card">
          <p className="section-title">Card usage trend</p>
          <p className="section-subtitle">90-day change: {pct(data.card_spend_change_90d_pct)}</p>
          <TrendChart
            data={data.trends.map((t) => ({ month: t.activity_month, value: t.card_spend_amount }))}
            color="#EA4335"
            formatValue={money}
          />
        </div>
        <div className="card">
          <p className="section-title">App usage trend</p>
          <p className="section-subtitle">
            90-day change: {pct(data.login_change_90d_pct)} · {data.days_since_last_login} days since last login
          </p>
          <TrendChart
            data={data.trends.map((t) => ({ month: t.activity_month, value: t.login_count }))}
            color="#34A853"
            formatValue={(v) => `${v} logins`}
          />
        </div>
      </div>

      <div className="card">
        <p className="section-title">Contact and complaint history</p>
        {data.contact_history.length === 0 ? (
          <p className="section-subtitle">No contacts on record.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Channel</th>
                <th scope="col">Reason</th>
                <th scope="col">Complaint</th>
                <th scope="col">Resolved</th>
                <th scope="col">Satisfaction</th>
              </tr>
            </thead>
            <tbody>
              {data.contact_history.map((c, i) => (
                <tr key={i}>
                  <td>{c.contact_date}</td>
                  <td>{c.channel}</td>
                  <td>{c.reason}</td>
                  <td>{c.is_complaint ? "Yes" : "No"}</td>
                  <td>{c.is_resolved ? "Yes" : "No"}</td>
                  <td>{c.satisfaction_score} / 5</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
