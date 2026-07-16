interface Series {
  label: string;
  color: string;
  values: number[];
}

interface Props {
  series: Series[];
  periodLabels: string[];
}

const CHART_WIDTH = 320;
const CHART_HEIGHT = 120;
const PADDING_X = 12;
const PADDING_Y = 12;

function buildPoints(values: number[], maxValue: number): string {
  const usableWidth = CHART_WIDTH - PADDING_X * 2;
  const usableHeight = CHART_HEIGHT - PADDING_Y * 2;
  const step = values.length > 1 ? usableWidth / (values.length - 1) : 0;

  return values
    .map((value, index) => {
      const x = PADDING_X + step * index;
      const ratio = maxValue > 0 ? value / maxValue : 0;
      const y = PADDING_Y + usableHeight * (1 - ratio);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function UsageTrendChart({ series, periodLabels }: Props) {
  const maxValue = Math.max(1, ...series.flatMap((s) => s.values));

  return (
    <div className="usage-trend-chart">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="利用推移グラフ"
        className="usage-trend-chart__svg"
      >
        <line
          x1={PADDING_X}
          y1={CHART_HEIGHT - PADDING_Y}
          x2={CHART_WIDTH - PADDING_X}
          y2={CHART_HEIGHT - PADDING_Y}
          className="usage-trend-chart__axis"
        />
        {series.map((s) => (
          <polyline
            key={s.label}
            points={buildPoints(s.values, maxValue)}
            fill="none"
            stroke={s.color}
            strokeWidth={2.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {series.map((s) =>
          s.values.map((value, index) => {
            const usableWidth = CHART_WIDTH - PADDING_X * 2;
            const step = s.values.length > 1 ? usableWidth / (s.values.length - 1) : 0;
            const x = PADDING_X + step * index;
            const ratio = maxValue > 0 ? value / maxValue : 0;
            const y = PADDING_Y + (CHART_HEIGHT - PADDING_Y * 2) * (1 - ratio);
            return <circle key={`${s.label}-${index}`} cx={x} cy={y} r={3} fill={s.color} />;
          }),
        )}
      </svg>
      <div className="usage-trend-chart__x-labels">
        {periodLabels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      <div className="usage-trend-chart__legend">
        {series.map((s) => (
          <span key={s.label} className="usage-trend-chart__legend-item">
            <span
              className="usage-trend-chart__legend-swatch"
              style={{ backgroundColor: s.color }}
              aria-hidden="true"
            />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
