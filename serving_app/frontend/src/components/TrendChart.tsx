import { useMemo, useState, type PointerEvent } from 'react'

// dataviz skillの方針: line/areaチャートはデフォルトでクロスヘア＋ツールチップを
// 備える。ライブラリに頼らず、SVG＋ホバー読み取り欄（fragileな絶対位置ツール
// チップの代わり）で実装する。

export interface TrendPoint {
  period: string
  value: number
}

export interface TrendSeriesData {
  id: string
  label: string
  colorVar: string
  points: TrendPoint[] // periods配列と同じ長さ・同じ順序で揃えること
}

interface TrendChartProps {
  periods: string[]
  series: TrendSeriesData[]
  valueFormatter?: (value: number) => string
}

const WIDTH = 640
const HEIGHT = 260
const MARGIN = { top: 16, right: 16, bottom: 32, left: 56 }

function formatPeriodLabel(period: string): string {
  const [year, month] = period.split('-')
  return `${year}/${month}`
}

export function TrendChart({ periods, series, valueFormatter }: TrendChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const format = valueFormatter ?? ((v: number) => v.toLocaleString('ja-JP'))

  const plotWidth = WIDTH - MARGIN.left - MARGIN.right
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom

  const maxValue = useMemo(() => {
    const allValues = series.flatMap((s) => s.points.map((p) => p.value))
    return Math.max(1, ...allValues) * 1.1
  }, [series])

  const xAt = (i: number) =>
    MARGIN.left + (periods.length > 1 ? (i * plotWidth) / (periods.length - 1) : plotWidth / 2)
  const yAt = (v: number) => MARGIN.top + plotHeight - (v / maxValue) * plotHeight

  const handlePointerMove = (event: PointerEvent<SVGRectElement>) => {
    // rectはSVGのviewBox座標(plotWidth=568等)で描画されているが、実際に
    // ブラウザ上でレンダリングされるサイズはレスポンシブに拡大縮小される
    // （getBoundingClientRect()は実ピクセル単位を返す）。plotWidthで割ると
    // 単位が食い違い、ratioが常に1を超えて範囲外にクランプされ続けて
    // ホバーが機能しなくなるため、必ずrect.width（実表示幅）で正規化する。
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = rect.width > 0 ? (event.clientX - rect.left) / rect.width : 0
    const index = Math.round(ratio * Math.max(periods.length - 1, 0))
    setHoverIndex(Math.min(Math.max(index, 0), periods.length - 1))
  }

  // 均等間隔で最大6個のティックを選ぶ（最初と最後を必ず含み、末尾で
  // ラベルが詰まって重なるのを防ぐ）
  const tickIndices = useMemo(() => {
    const tickCount = Math.min(6, periods.length)
    if (tickCount <= 1) return periods.map((_, i) => i)
    const indices = new Set<number>()
    for (let i = 0; i < tickCount; i += 1) {
      indices.add(Math.round((i * (periods.length - 1)) / (tickCount - 1)))
    }
    return Array.from(indices)
  }, [periods])

  return (
    <div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="店舗別売上の月次推移"
        style={{ width: '100%', height: 'auto' }}
      >
        {[0, 0.5, 1].map((t) => (
          <line
            key={t}
            x1={MARGIN.left}
            x2={WIDTH - MARGIN.right}
            y1={MARGIN.top + plotHeight * (1 - t)}
            y2={MARGIN.top + plotHeight * (1 - t)}
            stroke="var(--gridline)"
            strokeWidth={1}
          />
        ))}

        {series.map((s) => (
          <path
            key={s.id}
            d={s.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(p.value)}`).join(' ')}
            fill="none"
            stroke={s.colorVar}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {series.map((s) =>
          s.points.map((p, i) => (
            <circle key={`${s.id}-${i}`} cx={xAt(i)} cy={yAt(p.value)} r={3.5} fill={s.colorVar} />
          )),
        )}

        {hoverIndex !== null && (
          <line
            x1={xAt(hoverIndex)}
            x2={xAt(hoverIndex)}
            y1={MARGIN.top}
            y2={MARGIN.top + plotHeight}
            stroke="var(--text-muted)"
            strokeWidth={1}
            strokeDasharray="3 3"
          />
        )}

        {periods.map((p, i) => {
          if (!tickIndices.includes(i)) return null
          // 先頭・末尾のラベルはmiddle基準だとviewBox外にはみ出して欠けるため、
          // 端はテキストの内側の端で揃える
          const anchor = i === 0 ? 'start' : i === periods.length - 1 ? 'end' : 'middle'
          return (
            <text
              key={p}
              x={xAt(i)}
              y={HEIGHT - 8}
              textAnchor={anchor}
              fontSize={11}
              fill="var(--text-muted)"
            >
              {formatPeriodLabel(p)}
            </text>
          )
        })}

        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={plotWidth}
          height={plotHeight}
          fill="transparent"
          style={{ pointerEvents: 'all' }}
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setHoverIndex(null)}
        />
      </svg>

      <div className="trend-readout">
        {hoverIndex !== null ? (
          <>
            <strong>{formatPeriodLabel(periods[hoverIndex])}</strong>
            <span className="trend-readout-values">
              {series.map((s) => (
                <span key={s.id} className="trend-readout-item">
                  <span className="legend-swatch" style={{ background: s.colorVar }} />
                  {s.label}: {format(s.points[hoverIndex]?.value ?? 0)}
                </span>
              ))}
            </span>
          </>
        ) : (
          <span className="trend-readout-placeholder">
            グラフにカーソルを合わせると月別の値を表示します
          </span>
        )}
      </div>

      {series.length > 1 && (
        <div className="legend">
          {series.map((s) => (
            <span className="legend-item" key={s.id}>
              <span className="legend-swatch" style={{ background: s.colorVar }} />
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
