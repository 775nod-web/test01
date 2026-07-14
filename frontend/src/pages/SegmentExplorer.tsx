import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import type { CustomerListItem, SegmentFilterOptions } from "../types";

function pct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(0)}%`;
}

export function SegmentExplorer() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<SegmentFilterOptions | null>(null);
  const [riskSegment, setRiskSegment] = useState("");
  const [valueSegment, setValueSegment] = useState("");
  const [balanceDecline, setBalanceDecline] = useState(false);
  const [cardDecline, setCardDecline] = useState(false);
  const [appDecline, setAppDecline] = useState(false);
  const [complaintsOnly, setComplaintsOnly] = useState(false);
  const [maxProducts, setMaxProducts] = useState("");

  const [items, setItems] = useState<CustomerListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.segmentFilterOptions().then(setOptions).catch(() => setOptions({ risk_segments: [], value_segments: [] }));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .customers({
        risk_segment: riskSegment || undefined,
        value_segment: valueSegment || undefined,
        max_product_count: maxProducts ? Number(maxProducts) : undefined,
        balance_decline_pct: balanceDecline ? -0.3 : undefined,
        card_spend_decline_pct: cardDecline ? -0.3 : undefined,
        app_decline_pct: appDecline ? -0.5 : undefined,
        min_complaints_90d: complaintsOnly ? 2 : undefined,
        limit: 200,
      })
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load customers."))
      .finally(() => setLoading(false));
  }, [riskSegment, valueSegment, balanceDecline, cardDecline, appDecline, complaintsOnly, maxProducts]);

  return (
    <div>
      <PageHeader
        title="Segment Explorer"
        question="Which customer behavior pattern should the campaign address?"
      />

      <div className="card">
        <div className="filters-row">
          <div className="filter-field">
            <label htmlFor="risk-filter">Risk segment</label>
            <select id="risk-filter" value={riskSegment} onChange={(e) => setRiskSegment(e.target.value)}>
              <option value="">All</option>
              {(options?.risk_segments ?? []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="value-filter">Value segment</label>
            <select id="value-filter" value={valueSegment} onChange={(e) => setValueSegment(e.target.value)}>
              <option value="">All</option>
              {(options?.value_segments ?? []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="max-products">Product holdings</label>
            <select id="max-products" value={maxProducts} onChange={(e) => setMaxProducts(e.target.value)}>
              <option value="">Any</option>
              <option value="1">1 or fewer</option>
              <option value="2">2 or fewer</option>
              <option value="3">3 or fewer</option>
            </select>
          </div>
        </div>
        <div className="checkbox-row">
          <label className="checkbox-field">
            <input type="checkbox" checked={balanceDecline} onChange={(e) => setBalanceDecline(e.target.checked)} />
            Balance decline (&gt;30%, 90d)
          </label>
          <label className="checkbox-field">
            <input type="checkbox" checked={cardDecline} onChange={(e) => setCardDecline(e.target.checked)} />
            Card spend decline (&gt;30%, 90d)
          </label>
          <label className="checkbox-field">
            <input type="checkbox" checked={appDecline} onChange={(e) => setAppDecline(e.target.checked)} />
            App engagement decline (&gt;50%, 90d)
          </label>
          <label className="checkbox-field">
            <input type="checkbox" checked={complaintsOnly} onChange={(e) => setComplaintsOnly(e.target.checked)} />
            2+ complaints (90d)
          </label>
        </div>

        {error && <ErrorState message={error} />}
        {!error && loading && <LoadingState label="Loading customers…" />}
        {!error && !loading && items && items.length === 0 && <EmptyState />}
        {!error && !loading && items && items.length > 0 && (
          <>
            <p className="section-subtitle">{items.length} customers match (showing up to 200).</p>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Customer</th>
                    <th scope="col">Risk</th>
                    <th scope="col">Value</th>
                    <th scope="col">Primary driver</th>
                    <th scope="col">Balance Δ 90d</th>
                    <th scope="col">Card Δ 90d</th>
                    <th scope="col">App Δ 90d</th>
                    <th scope="col">Complaints 90d</th>
                    <th scope="col">Recommended action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr
                      key={c.customer_id}
                      onClick={() => navigate(`/customers/${c.customer_id}`)}
                      tabIndex={0}
                      role="button"
                      aria-label={`Open Customer 360 for ${c.customer_id}`}
                      onKeyDown={(e) => e.key === "Enter" && navigate(`/customers/${c.customer_id}`)}
                    >
                      <td>{c.customer_id}</td>
                      <td>
                        <RiskBadge segment={c.risk_segment} />
                      </td>
                      <td>
                        <ValueBadge segment={c.value_segment} />
                      </td>
                      <td>{c.primary_driver}</td>
                      <td>{pct(c.balance_change_90d_pct)}</td>
                      <td>{pct(c.card_spend_change_90d_pct)}</td>
                      <td>{pct(c.login_change_90d_pct)}</td>
                      <td>{c.complaint_count_90d}</td>
                      <td>{c.recommended_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
