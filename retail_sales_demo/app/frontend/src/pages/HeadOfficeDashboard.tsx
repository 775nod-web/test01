import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { fetchAlerts, fetchDailyStoreSales, fetchKpiSummary } from "../api/client";
import type { AlertRow, DailyStoreSales, KpiSummary } from "../types";
import { KpiCard } from "../components/KpiCard";
import { AlertBanner } from "../components/AlertBanner";

export function HeadOfficeDashboard() {
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [dailySales, setDailySales] = useState<DailyStoreSales[]>([]);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);

  useEffect(() => {
    fetchKpiSummary().then(setKpi).catch(console.error);
    fetchDailyStoreSales().then(setDailySales).catch(console.error);
    fetchAlerts().then(setAlerts).catch(console.error);
  }, []);

  // 店舗横断で日付ごとの売上を集計してチャート用データに変換する
  const trend = Object.values(
    dailySales.reduce<Record<string, { sales_date: string; total_sales_amount: number }>>((acc, row) => {
      const key = row.sales_date;
      if (!acc[key]) {
        acc[key] = { sales_date: key, total_sales_amount: 0 };
      }
      acc[key].total_sales_amount += row.total_sales_amount;
      return acc;
    }, {})
  ).sort((a, b) => a.sales_date.localeCompare(b.sales_date));

  return (
    <div>
      <h2>本社経営ダッシュボード</h2>
      <AlertBanner alerts={alerts} />

      {kpi && (
        <div className="kpi-grid">
          <KpiCard label="Net Sales" value={kpi.net_sales.toLocaleString()} accentColor="var(--color-primary)" />
          <KpiCard
            label="Gross Sales"
            value={kpi.gross_sales.toLocaleString()}
            note={kpi.gross_sales_is_estimated ? "※discount集約列が未整備のため暫定値（net salesと同値）" : undefined}
            accentColor="var(--color-accent)"
          />
          <KpiCard label="Transaction Count" value={kpi.transaction_count.toLocaleString()} accentColor="var(--color-positive)" />
          <KpiCard label="Units Sold" value={kpi.units_sold.toLocaleString()} accentColor="var(--color-warning)" />
          <KpiCard
            label="Average Basket Size"
            value={kpi.average_basket_size.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            accentColor="var(--color-negative)"
          />
        </div>
      )}

      <div className="card">
        <h3>日別売上推移（全店舗合計）</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="sales_date" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey="total_sales_amount" stroke="#aecbfa" strokeWidth={3} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
