import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CategorySalesPoint } from '../../types';

const BAR_COLORS = [
  'var(--pastel-blue)',
  'var(--pastel-green)',
  'var(--pastel-coral)',
  'var(--pastel-yellow)',
  'var(--pastel-purple)',
];

interface Props {
  data: CategorySalesPoint[];
}

export function CategorySalesChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, left: 24, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis type="number" tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey="category_name" tick={{ fontSize: 12 }} width={100} />
        <Tooltip
          formatter={(value, _name, item) => {
            const numericValue = Number(value ?? 0);
            const share = ((item.payload as CategorySalesPoint).share_of_net_sales ?? 0) * 100;
            return [`${numericValue.toLocaleString()} (${share.toFixed(1)}%)`, '売上'];
          }}
        />
        <Bar dataKey="net_sales">
          {data.map((entry, i) => (
            <Cell key={entry.category_id} fill={BAR_COLORS[i % BAR_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
