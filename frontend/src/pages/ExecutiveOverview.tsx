import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { BarChart, type BarDatum } from "../components/BarChart";
import { PageHeader } from "../components/Layout";
import { KpiTile } from "../components/KpiTile";
import { ErrorState, LoadingState } from "../components/States";
import { ValueRiskMatrix } from "../components/ValueRiskMatrix";
import type { KpiResponse, RiskDistributionItem, TopDriverItem, ValueRiskMatrixItem } from "../types";

const RISK_COLOR: Record<string, string> = { High: "#EA4335", Medium: "#FBBC04", Low: "#34A853" };

export function ExecutiveOverview() {
  const [kpis, setKpis] = useState<KpiResponse | null>(null);
  const [riskDist, setRiskDist] = useState<RiskDistributionItem[] | null>(null);
  const [matrix, setMatrix] = useState<ValueRiskMatrixItem[] | null>(null);
  const [drivers, setDrivers] = useState<TopDriverItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.kpis(), api.riskDistribution(), api.valueRiskMatrix(), api.topRiskDrivers()])
      .then(([k, r, m, d]) => {
        setKpis(k);
        setRiskDist(r);
        setMatrix(m);
        setDrivers(d);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load data."));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!kpis || !riskDist || !matrix || !drivers) return <LoadingState label="Loading executive overview…" />;

  const prioritizedPctRaw = kpis.broad_campaign_audience_count
    ? (100 * kpis.prioritized_audience_count) / kpis.broad_campaign_audience_count
    : 0;
  const prioritizedPctLabel =
    prioritizedPctRaw > 0 && prioritizedPctRaw < 1 ? "<1%" : `${Math.round(prioritizedPctRaw)}%`;

  const driverBars: BarDatum[] = drivers.map((d) => ({
    label: d.primary_driver,
    value: d.customer_count,
    color: "#4285F4",
  }));

  return (
    <div>
      <PageHeader
        title="Executive Overview"
        question="Where should we focus limited retention budget?"
      />

      <div className="grid grid--kpis">
        <KpiTile label="Total customers" value={kpis.total_customers.toLocaleString()} />
        <KpiTile
          label="High-risk customers"
          value={kpis.high_risk_customers.toLocaleString()}
          variant="risk"
        />
        <KpiTile
          label="High-risk & high-value"
          value={kpis.high_risk_high_value_customers.toLocaleString()}
          variant="risk"
          tooltip="Customers who are both High risk and High value — the top retention priority."
        />
        <KpiTile
          label="Estimated value at risk"
          value={`$${Math.round(kpis.estimated_value_at_risk_total_simulated).toLocaleString()}`}
          variant="value"
          footnote="Simulated figure — not a real financial estimate."
        />
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <p className="section-title">Broad campaign vs. prioritized audience</p>
        <p className="section-subtitle">
          Today's approach contacts everyone. Prioritizing high-risk, high/medium-value
          customers narrows the audience to {prioritizedPctLabel} of the book.
        </p>
        <div className="grid grid--kpis">
          <KpiTile label="Broad campaign audience" value={kpis.broad_campaign_audience_count.toLocaleString()} />
          <KpiTile
            label="Prioritized audience"
            value={kpis.prioritized_audience_count.toLocaleString()}
            variant="value"
            tooltip="High risk and High or Medium value."
          />
        </div>
      </div>

      <div className="grid grid--2col" style={{ marginTop: 20 }}>
        <div className="card">
          <p className="section-title">Risk distribution</p>
          <p className="section-subtitle">How many customers fall into each risk segment.</p>
          <BarChart
            data={riskDist.map((r) => ({
              label: `${r.risk_segment} (avg score ${r.avg_risk_score})`,
              value: r.customer_count,
              color: RISK_COLOR[r.risk_segment],
            }))}
          />
        </div>

        <div className="card">
          <p className="section-title">Customer value vs. churn risk</p>
          <p className="section-subtitle">
            Risk and value are independent — high-value customers are not automatically low risk.
          </p>
          <ValueRiskMatrix data={matrix} />
        </div>
      </div>

      <div className="card">
        <p className="section-title">Top risk drivers</p>
        <p className="section-subtitle">
          Which behavior pattern is driving the most at-risk customers across the book.
        </p>
        <BarChart data={driverBars} />
      </div>
    </div>
  );
}
