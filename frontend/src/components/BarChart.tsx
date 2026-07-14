export interface BarDatum {
  label: string;
  value: number;
  color: string;
  valueLabel?: string;
}

// Simple horizontal bar chart. Every bar carries a visible text label and a
// direct numeric value label — color is never the only way to read a value
// (see dataviz skill: "text wears text tokens, never the series color").
export function BarChart({ data }: { data: BarDatum[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="bar-chart" role="img" aria-label={data.map((d) => `${d.label}: ${d.valueLabel ?? d.value}`).join(", ")}>
      {data.map((d) => (
        <div className="bar-chart__row" key={d.label}>
          <span className="bar-chart__label">{d.label}</span>
          <div className="bar-chart__track">
            <div
              className="bar-chart__fill"
              style={{ width: `${(d.value / max) * 100}%`, background: d.color }}
            />
          </div>
          <span className="bar-chart__value">{d.valueLabel ?? d.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}
