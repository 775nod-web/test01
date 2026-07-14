import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import type { LossSeriesPoint } from "../../types";
import { formatJpy, formatShortDate } from "../../utils/format";

interface LossChartProps {
  data: LossSeriesPoint[];
}

function yenTick(value: number): string {
  return `¥${Math.round(value / 10000).toLocaleString("ja-JP")}万`;
}

function LossChart({ data }: LossChartProps) {
  const chartData = data.map((p) => ({ ...p, label: formatShortDate(p.date) }));

  return (
    <section className="card chart-card" aria-labelledby="loss-chart-heading">
      <h2 id="loss-chart-heading">不正損失額・推定防止損失額の推移</h2>
      <p className="chart-caption">単位: 円。日別の不正損失額と、検知により防止できたと推定される金額です。</p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DADCE0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={yenTick} width={64} tick={{ fontSize: 12 }} />
          <RechartsTooltip formatter={(v: number) => formatJpy(v)} labelFormatter={(l) => `日付: ${l}`} />
          <Legend
            formatter={(value: string) => (value === "fraud_loss_amount" ? "不正損失額" : "推定防止損失額")}
          />
          <Bar dataKey="fraud_loss_amount" name="fraud_loss_amount" fill="#EA4335" radius={[4, 4, 0, 0]} />
          <Bar dataKey="prevented_loss_amount" name="prevented_loss_amount" fill="#34A853" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}

export default LossChart;
