import type { CSSProperties } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { ErrorView, LoadingView } from "../components/StateViews";
import { useAsyncData } from "../hooks/useAsyncData";
import { chartSeries, gridline, ink, status } from "../theme/colors";
import type { SalesPerPlan as SalesPerPlanRow } from "../api/types";

const PLAN_ORDER = ["starter", "pro", "enterprise"];
const PLAN_COLOR: Record<string, string> = {
  starter: chartSeries[0],
  pro: chartSeries[1],
  enterprise: chartSeries[4],
};

function formatYen(value: number): string {
  return `¥${Math.round(value).toLocaleString("ja-JP")}`;
}

function formatMonthJp(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}/${d.getMonth() + 1}`;
}

function buildChartData(rows: SalesPerPlanRow[]) {
  const months = Array.from(new Set(rows.map((r) => r.sales_month))).sort();
  return months.map((month) => {
    const entry: Record<string, string | number> = { month: formatMonthJp(month) };
    for (const plan of PLAN_ORDER) {
      const row = rows.find((r) => r.sales_month === month && r.plan_type === plan);
      entry[plan] = row?.total_revenue ?? 0;
    }
    return entry;
  });
}

export function SalesPerPlan() {
  const state = useAsyncData(() => api.getSalesPerPlan(12), []);

  return (
    <div>
      <header style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, color: ink.primary, margin: 0 }}>プラン別売上</h1>
        <p style={{ fontSize: 13, color: ink.secondary, margin: "4px 0 0" }}>
          プラン別・月別の売上と決済失敗率から、収益が停滞しているプランを特定する（事業企画・プロダクト向け）
        </p>
      </header>

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView message={state.error} />}
      {state.status === "success" && (() => {
        const rows = state.data;
        const chartData = buildChartData(rows);

        return (
          <>
            <section
              style={{
                background: "#ffffff",
                borderRadius: 14,
                padding: "16px 20px",
                marginBottom: 24,
                border: "1px solid rgba(11,11,11,0.08)",
              }}
            >
              <h2 style={{ fontSize: 14, fontWeight: 600, color: ink.primary, margin: "0 0 12px" }}>
                月次売上（プラン別）
              </h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke={gridline} vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 12, fill: ink.muted }} />
                  <YAxis tick={{ fontSize: 12, fill: ink.muted }} tickFormatter={(v) => `¥${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v: number) => formatYen(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {PLAN_ORDER.map((plan) => (
                    <Bar key={plan} dataKey={plan} name={plan} stackId="revenue" fill={PLAN_COLOR[plan]} radius={[0, 0, 0, 0]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </section>

            <SalesTable rows={rows} />
          </>
        );
      })()}
    </div>
  );
}

function SalesTable({ rows }: { rows: SalesPerPlanRow[] }) {
  const sorted = [...rows].sort((a, b) => (a.sales_month < b.sales_month ? 1 : -1));
  return (
    <section style={{ background: "#ffffff", borderRadius: 14, padding: "8px 0", border: "1px solid rgba(11,11,11,0.08)" }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: ink.muted, borderBottom: `1px solid ${gridline}` }}>
              <th style={th}>月</th>
              <th style={th}>プラン</th>
              <th style={th}>売上</th>
              <th style={th}>前月比</th>
              <th style={th}>平均単価</th>
              <th style={th}>有効契約数</th>
              <th style={th}>解約数</th>
              <th style={th}>決済失敗率</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const isStagnant = (r.failed_payment_rate ?? 0) > 0.1;
              return (
                <tr key={`${r.sales_month}-${r.plan_type}`} style={{ borderBottom: `1px solid ${gridline}` }}>
                  <td style={td}>{formatMonthJp(r.sales_month)}</td>
                  <td style={td}>{r.plan_type}</td>
                  <td style={td}>{formatYen(r.total_revenue)}</td>
                  <td style={{ ...td, color: (r.revenue_mom_change_rate ?? 0) < 0 ? status.critical : status.good }}>
                    {r.revenue_mom_change_rate != null ? `${(r.revenue_mom_change_rate * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td style={td}>{r.avg_transaction_amount != null ? formatYen(r.avg_transaction_amount) : "—"}</td>
                  <td style={td}>{r.active_subscriber_count.toLocaleString()}</td>
                  <td style={td}>{r.churned_subscriber_count.toLocaleString()}</td>
                  <td style={{ ...td, fontWeight: isStagnant ? 700 : 400, color: isStagnant ? status.critical : ink.primary }}>
                    {r.failed_payment_rate != null ? `${(r.failed_payment_rate * 100).toFixed(1)}%` : "—"}
                    {isStagnant && " ⚠"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const th: CSSProperties = { padding: "10px 16px", fontWeight: 600 };
const td: CSSProperties = { padding: "10px 16px" };
