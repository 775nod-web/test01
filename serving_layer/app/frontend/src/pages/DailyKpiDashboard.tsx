import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { KpiCard } from "../components/KpiCard";
import { ErrorView, LoadingView } from "../components/StateViews";
import { useAsyncData } from "../hooks/useAsyncData";
import { chartSeries, gridline, ink, uiPastel } from "../theme/colors";

const PERIOD_OPTIONS = [
  { label: "直近7日", days: 7 },
  { label: "直近30日", days: 30 },
  { label: "直近90日", days: 90 },
];

function formatYen(value: number): string {
  return `¥${Math.round(value).toLocaleString("ja-JP")}`;
}

function formatDateJp(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function DailyKpiDashboard() {
  const [days, setDays] = useState(30);
  const state = useAsyncData(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    const toIso = (d: Date) => d.toISOString().slice(0, 10);
    return api.getDailyKpi(toIso(start), toIso(end));
  }, [days]);

  return (
    <div>
      <header style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, color: ink.primary, margin: 0 }}>経営KPIダッシュボード</h1>
        <p style={{ fontSize: 13, color: ink.secondary, margin: "4px 0 0" }}>
          売上・DAU・新規登録・有料転換・解約を日次で一覧化し、事業の調子を素早く把握する（経営層向け）
        </p>
      </header>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.days}
            onClick={() => setDays(opt.days)}
            style={{
              padding: "6px 14px",
              borderRadius: 999,
              border: "none",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              background: days === opt.days ? uiPastel.blue : "#ffffff",
              color: ink.primary,
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {state.status === "loading" && <LoadingView />}
      {state.status === "error" && <ErrorView message={state.error} />}
      {state.status === "success" && (() => {
        const rows = state.data;
        const latest = rows[rows.length - 1];
        const chartData = rows.map((r) => ({ ...r, label: formatDateJp(r.kpi_date) }));

        return (
          <>
            {latest && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginBottom: 28 }}>
                <KpiCard label="DAU（当日）" value={latest.dau.toLocaleString()} accent={uiPastel.blue} />
                <KpiCard
                  label="有料ユーザー数"
                  value={latest.total_paid_users.toLocaleString()}
                  accent={uiPastel.green}
                  sub={`無料ユーザー ${latest.total_free_users.toLocaleString()}`}
                />
                <KpiCard label="当日売上" value={formatYen(latest.daily_revenue)} accent={uiPastel.yellow} />
                <KpiCard
                  label="無料→有料転換率"
                  value={latest.free_to_paid_rate != null ? `${(latest.free_to_paid_rate * 100).toFixed(1)}%` : "—"}
                  accent={uiPastel.purple}
                  sub={`新規登録 ${latest.new_signup_count} 件`}
                />
              </div>
            )}

            <ChartCard title="売上推移">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke={gridline} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: ink.muted }} />
                  <YAxis tick={{ fontSize: 12, fill: ink.muted }} tickFormatter={(v) => `¥${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v: number) => formatYen(v)} />
                  <Line type="monotone" dataKey="daily_revenue" name="日次売上" stroke={chartSeries[0]} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="DAU推移">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke={gridline} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: ink.muted }} />
                  <YAxis tick={{ fontSize: 12, fill: ink.muted }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="dau" name="DAU" stroke={chartSeries[1]} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="新規登録 vs 解約">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke={gridline} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: ink.muted }} />
                  <YAxis tick={{ fontSize: 12, fill: ink.muted }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="new_signup_count" name="新規登録" fill={chartSeries[3]} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="churn_count" name="解約" fill={chartSeries[5]} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="転換意向 vs 解約意向（クリックイベント数）">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke={gridline} vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12, fill: ink.muted }} />
                  <YAxis tick={{ fontSize: 12, fill: ink.muted }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="upgrade_click_count" name="アップグレードクリック" fill={chartSeries[2]} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="cancel_click_count" name="解約クリック" fill={chartSeries[5]} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </>
        );
      })()}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section
      style={{
        background: "#ffffff",
        borderRadius: 14,
        padding: "16px 20px",
        marginBottom: 20,
        border: "1px solid rgba(11,11,11,0.08)",
      }}
    >
      <h2 style={{ fontSize: 14, fontWeight: 600, color: ink.primary, margin: "0 0 12px" }}>{title}</h2>
      {children}
    </section>
  );
}
