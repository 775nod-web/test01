import { useState } from "react";

export interface TrendPoint {
  month: string;
  value: number;
}

// Single-series line chart (no legend needed — the title names the series,
// per dataviz skill). Ships a hover tooltip since any line/area chart is
// interactive by default.
export function TrendChart({
  data,
  color,
  formatValue,
  height = 140,
}: {
  data: TrendPoint[];
  color: string;
  formatValue: (v: number) => string;
  height?: number;
}) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const width = 560;
  const padding = 24;

  if (data.length === 0) {
    return <p className="section-subtitle">No trend data available.</p>;
  }

  const values = data.map((d) => d.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const xFor = (i: number) => padding + (i / Math.max(1, data.length - 1)) * (width - 2 * padding);
  const yFor = (v: number) => height - padding - ((v - minV) / range) * (height - 2 * padding);

  const pathD = data.map((d, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(d.value)}`).join(" ");

  return (
    <div className="trend-chart-wrap">
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Trend from ${data[0].month} to ${data[data.length - 1].month}`}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="var(--border)" strokeWidth={1} />
        <path d={pathD} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => (
          <circle
            key={d.month}
            cx={xFor(i)}
            cy={yFor(d.value)}
            r={hoverIdx === i ? 5 : 3}
            fill={color}
            onMouseEnter={() => setHoverIdx(i)}
            style={{ cursor: "pointer" }}
          />
        ))}
        {/* invisible wider hit-targets for easier hover per-point */}
        {data.map((d, i) => (
          <rect
            key={`hit-${d.month}`}
            x={xFor(i) - (width / data.length) / 2}
            y={0}
            width={width / data.length}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHoverIdx(i)}
          />
        ))}
      </svg>
      {hoverIdx !== null && (
        <div
          className="trend-tooltip"
          style={{
            left: `${(xFor(hoverIdx) / width) * 100}%`,
            top: `${(yFor(data[hoverIdx].value) / height) * 100}%`,
          }}
        >
          {data[hoverIdx].month}: {formatValue(data[hoverIdx].value)}
        </div>
      )}
      <div className="section-subtitle" style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
        <span>{data[0].month}</span>
        <span>{data[data.length - 1].month}</span>
      </div>
    </div>
  );
}
