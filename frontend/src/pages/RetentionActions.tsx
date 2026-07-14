import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { HumanReviewBadge, RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import type { RetentionActionItem } from "../types";

const PAGE_SIZE = 25;

export function RetentionActions() {
  const navigate = useNavigate();
  const [riskSegment, setRiskSegment] = useState("");
  const [valueSegment, setValueSegment] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<RetentionActionItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setOffset(0);
  }, [riskSegment, valueSegment]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .retentionActions({
        risk_segment: riskSegment || undefined,
        value_segment: valueSegment || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load retention actions."))
      .finally(() => setLoading(false));
  }, [riskSegment, valueSegment, offset]);

  const exportUrl = api.retentionActionsExportUrl({
    risk_segment: riskSegment || undefined,
    value_segment: valueSegment || undefined,
  });

  return (
    <div>
      <PageHeader title="Retention Actions" question="Who should receive which action first?" />

      <div className="card">
        <div className="filters-row">
          <div className="filter-field">
            <label htmlFor="ra-risk">Risk segment</label>
            <select id="ra-risk" value={riskSegment} onChange={(e) => setRiskSegment(e.target.value)}>
              <option value="">High + Medium</option>
              <option value="High">High only</option>
              <option value="Medium">Medium only</option>
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="ra-value">Value segment</label>
            <select id="ra-value" value={valueSegment} onChange={(e) => setValueSegment(e.target.value)}>
              <option value="">All</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <a className="btn btn--primary" href={exportUrl} download style={{ textDecoration: "none" }}>
            Download CSV
          </a>
        </div>

        {error && <ErrorState message={error} />}
        {!error && loading && <LoadingState label="Loading retention actions…" />}
        {!error && !loading && items && items.length === 0 && <EmptyState message="No customers match this filter." />}
        {!error && !loading && items && items.length > 0 && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Priority</th>
                  <th scope="col">Customer</th>
                  <th scope="col">Risk</th>
                  <th scope="col">Value</th>
                  <th scope="col">Main driver</th>
                  <th scope="col">Recommended action</th>
                  <th scope="col">Channel</th>
                  <th scope="col">Est. value at risk</th>
                  <th scope="col">Review</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr
                    key={r.customer_id}
                    onClick={() => navigate(`/customers/${r.customer_id}`)}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open Customer 360 for ${r.customer_id}`}
                    onKeyDown={(e) => e.key === "Enter" && navigate(`/customers/${r.customer_id}`)}
                  >
                    <td>#{r.action_priority_rank}</td>
                    <td>{r.customer_id}</td>
                    <td>
                      <RiskBadge segment={r.risk_segment} />
                    </td>
                    <td>
                      <ValueBadge segment={r.value_segment} />
                    </td>
                    <td>{r.primary_driver}</td>
                    <td>{r.recommended_action}</td>
                    <td>{r.recommended_channel}</td>
                    <td>${Math.round(r.estimated_value_at_risk).toLocaleString()}</td>
                    <td>
                      <HumanReviewBadge required={r.human_review_required} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination-row">
              <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                Previous
              </button>
              <span>Showing {offset + 1}–{offset + items.length}</span>
              <button
                className="btn"
                disabled={items.length < PAGE_SIZE}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
