import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import type { DailyStoreSalesPoint } from '../../types';

const LINE_COLORS = [
  'var(--pastel-blue-text)',
  'var(--pastel-green-text)',
  'var(--pastel-coral-text)',
  'var(--pastel-yellow-text)',
  'var(--pastel-purple-text)',
];

interface Props {
  data: DailyStoreSalesPoint[];
}

/** Pivots the flat (date, store) rows into one row per date with one column per store, for a multi-line chart. */
function pivotByStore(data: DailyStoreSalesPoint[]) {
  const dates = [...new Set(data.map((d) => d.sales_date))].sort();
  const storeNames = [...new Set(data.map((d) => d.store_name))];
  const byDate = new Map<string, Record<string, number | string>>();
  for (const date of dates) {
    byDate.set(date, { sales_date: date });
  }
  for (const row of data) {
    byDate.get(row.sales_date)![row.store_name] = row.net_sales;
  }
  return { rows: dates.map((d) => byDate.get(d)!), storeNames };
}

export function DailyStoreSalesChart({ data }: Props) {
  const { rows, storeNames } = pivotByStore(data);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey="sales_date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        {storeNames.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={LINE_COLORS[i % LINE_COLORS.length]}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
