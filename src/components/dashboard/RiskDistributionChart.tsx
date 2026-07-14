import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";
import type { RiskDistributionBand } from "../../types";

interface RiskDistributionChartProps {
  data: RiskDistributionBand[];
}

function RiskDistributionChart({ data }: RiskDistributionChartProps) {
  const normalTotal = data.reduce((sum, b) => sum + b.normal_count, 0) || 1;
  const fraudTotal = data.reduce((sum, b) => sum + b.fraud_count, 0) || 1;

  const chartData = data.map((b) => ({
    label: `${b.band}リスク`,
    normal_count: b.normal_count,
    fraud_count: b.fraud_count,
    normal_share: (b.normal_count / normalTotal) * 100,
    fraud_share: (b.fraud_count / fraudTotal) * 100,
  }));

  return (
    <section className="card chart-card" aria-labelledby="risk-dist-heading">
      <h2 id="risk-dist-heading">リスクスコア帯別の正常・不正分布</h2>
      <p className="chart-caption">
        単位: 割合(%)。正常取引全体・確定不正取引全体それぞれに占める、低・中・高リスク帯の内訳を比較します。
        値が高リスク帯に偏っているほど、スコアによる分離ができていることを示します。
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#DADCE0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 12 }} />
          <RechartsTooltip
            formatter={(value: number, name: string, item) => {
              const raw = name === "normal_share" ? item.payload.normal_count : item.payload.fraud_count;
              return [`${value.toFixed(1)}%（${raw.toLocaleString("ja-JP")}件）`, name === "normal_share" ? "正常取引" : "確定不正取引"];
            }}
          />
          <Legend formatter={(value: string) => (value === "normal_share" ? "正常取引" : "確定不正取引")} />
          <Bar dataKey="normal_share" name="normal_share" fill="#4285F4" radius={[4, 4, 0, 0]} />
          <Bar dataKey="fraud_share" name="fraud_share" fill="#EA4335" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}

export default RiskDistributionChart;
