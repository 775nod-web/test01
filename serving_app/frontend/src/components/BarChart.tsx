// dataviz skillの方針に沿い、チャートライブラリに頼らずプレーンなHTML/CSSで
// マーク（棒）を組み立てる。色は「識別（カテゴリ）」の役割のみを担い、
// 数値は直接ラベルとして常に併記する（色だけに意味を持たせない）。

export interface BarChartDatum {
  label: string
  value: number
  colorVar: string
}

interface BarChartProps {
  data: BarChartDatum[]
  valueFormatter?: (value: number) => string
}

export function BarChart({ data, valueFormatter }: BarChartProps) {
  const max = Math.max(...data.map((d) => d.value), 1)
  const format = valueFormatter ?? ((v: number) => v.toLocaleString('ja-JP'))

  return (
    <div>
      <div className="bar-chart" role="img" aria-label="カテゴリ別の棒グラフ">
        {data.map((d) => (
          <div className="bar-row" key={d.label}>
            <span className="bar-row-label">{d.label}</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{ width: `${Math.max((d.value / max) * 100, 1)}%`, background: d.colorVar }}
              />
            </div>
            <span className="bar-row-value">{format(d.value)}</span>
          </div>
        ))}
      </div>
      <div className="legend">
        {data.map((d) => (
          <span className="legend-item" key={d.label}>
            <span className="legend-swatch" style={{ background: d.colorVar }} />
            {d.label}
          </span>
        ))}
      </div>
    </div>
  )
}
