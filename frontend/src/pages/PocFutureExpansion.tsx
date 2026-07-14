import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { PageHeader } from "../components/Layout";
import { ErrorState, LoadingState } from "../components/States";
import type { PocSummaryResponse } from "../types";

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card">
      <p className="section-title">{title}</p>
      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function PocFutureExpansion() {
  const [data, setData] = useState<PocSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .pocSummary()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load this page."));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="Loading…" />;

  return (
    <div>
      <PageHeader
        title="PoC & Future Expansion"
        question="What do we need to validate before a production decision?"
      />

      <div className="grid grid--2col">
        <ListCard title="What is synthetic in this demo" items={data.synthetic_elements} />
        <ListCard title="What must be tested with real bank data" items={data.must_validate_with_bank_data} />
        <ListCard title="Suggested PoC success metrics" items={data.poc_success_metrics} />
        <ListCard title="Databricks Free Edition limitations" items={data.free_edition_limitations} />
      </div>

      <div className="card">
        <p className="section-title">How Customer 360 extends to cross-sell</p>
        <p className="section-subtitle">{data.cross_sell_reuse_note}</p>
        {data.cross_sell_sample.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Customer</th>
                <th scope="col">Value</th>
                <th scope="col">Products held</th>
                <th scope="col">App engagement score</th>
              </tr>
            </thead>
            <tbody>
              {data.cross_sell_sample.map((c) => (
                <tr key={c.customer_id} style={{ cursor: "default" }}>
                  <td>{c.customer_id}</td>
                  <td>{c.value_segment}</td>
                  <td>{c.product_count}</td>
                  <td>{c.app_engagement_score?.toFixed(0) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data.ml_comparison.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <p className="section-title" style={{ margin: 0 }}>
              Model comparison
            </p>
            <span className="badge badge--optional">Optional — Phase 7</span>
          </div>
          <p className="section-subtitle">{data.ml_comparison_note}</p>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Approach</th>
                <th scope="col">Precision</th>
                <th scope="col">Recall</th>
                <th scope="col">ROC-AUC</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {data.ml_comparison.map((row) => (
                <tr key={row.approach} style={{ cursor: "default" }}>
                  <td>{row.approach}</td>
                  <td>{row.precision.toFixed(3)}</td>
                  <td>{row.recall.toFixed(3)}</td>
                  <td>{row.roc_auc.toFixed(3)}</td>
                  <td style={{ color: "var(--text-secondary)", fontSize: 12 }}>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="section-subtitle" style={{ marginTop: 12, marginBottom: 0 }}>
            The app always falls back to the rule-based score above regardless of this comparison
            — see docs/ml-comparison.md for full methodology.
          </p>
        </div>
      )}
    </div>
  );
}
