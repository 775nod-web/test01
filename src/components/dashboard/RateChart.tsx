import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RateSeriesPoint } from "../../types";
import { formatShortDate } from "../../utils/format";

interface RateChartProps {
  data: RateSeriesPoint[];
}

function percentTick(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function finePercentTick(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function RateChart({ data }: RateChartProps) {
  const chartData = data.map((p) => ({ ...p, label: formatShortDate(p.date) }));

  return (
    <section className="card chart-card" aria-labelledby="rate-chart-heading">
      <h2 id="rate-chart-heading">不正率・正常承認率の推移</h2>
      <p className="chart-caption">単位: %（取引件数に対する割合）。日別の推移を示します。</p>

      <div className="rate-chart-block">
        <h3 className="chart-subheading">
          <span className="legend-dot" style={{ background: "#EA4335" }} aria-hidden="true" />
          不正率
        </h3>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#DADCE0" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis
              tickFormatter={finePercentTick}
              width={56}
              tick={{ fontSize: 12 }}
              domain={[0, "dataMax"]}
            />
            <RechartsTooltip formatter={(v: number) => finePercentTick(v)} labelFormatter={(l) => `日付: ${l}`} />
            <Line
              type="monotone"
              dataKey="fraud_rate"
              name="不正率"
              stroke="#EA4335"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="rate-chart-block">
        <h3 className="chart-subheading">
          <span className="legend-dot" style={{ background: "#34A853" }} aria-hidden="true" />
          正常取引承認率
        </h3>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#DADCE0" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tickFormatter={percentTick} width={48} tick={{ fontSize: 12 }} domain={[0.8, 1]} />
            <RechartsTooltip formatter={(v: number) => percentTick(v)} labelFormatter={(l) => `日付: ${l}`} />
            <Line
              type="monotone"
              dataKey="normal_approval_rate"
              name="正常取引承認率"
              stroke="#34A853"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default RateChart;
