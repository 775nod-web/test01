import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { DailyStoreSales } from '../types'
import { TrendChart, type TrendSeriesData } from './TrendChart'

// 店舗の色は「出現順」ではなく「store_id順」で固定する。
// フィルタで系列数が変わっても、同じ店舗が同じ色を保つようにするため
// （dataviz skillの非交渉ルール: 色はエンティティに従い、ランクや表示順に従わない）。
const SERIES_VARS = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)',
]

export function DailyStoreSalesPanel() {
  const [data, setData] = useState<DailyStoreSales[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [storeFilter, setStoreFilter] = useState<string>('all')
  const [view, setView] = useState<'chart' | 'table'>('chart')

  useEffect(() => {
    api.dailyStoreSales().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  const stores = useMemo(() => {
    if (!data) return [] as Array<{ id: string; name: string }>
    const seen = new Map<string, string>()
    data.forEach((row) => seen.set(row.store_id, row.store_name))
    return Array.from(seen.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.id.localeCompare(b.id))
  }, [data])

  const storeColor = useMemo(() => {
    const map = new Map<string, string>()
    stores.forEach((store, index) => {
      map.set(store.id, SERIES_VARS[index] ?? 'var(--text-muted)')
    })
    return map
  }, [stores])

  const filtered = useMemo(() => {
    if (!data) return []
    if (storeFilter === 'all') return data
    return data.filter((row) => row.store_id === storeFilter)
  }, [data, storeFilter])

  // サンプルデータは日次では点が疎らなため、傾向を見やすくするため月次に丸めて
  // 集計する（gold_daily_store_salesの値をそのまま合算するのみで、Gold layer
  // 自体の再集計・スキーマ変更は行わない）
  const trend = useMemo(() => {
    if (!filtered.length) return { periods: [] as string[], series: [] as TrendSeriesData[] }

    const periodSet = new Set<string>()
    const byStore = new Map<string, { name: string; values: Map<string, number> }>()

    filtered.forEach((row) => {
      const period = row.sales_date.slice(0, 7) // "YYYY-MM"
      periodSet.add(period)
      if (!byStore.has(row.store_id)) {
        byStore.set(row.store_id, { name: row.store_name, values: new Map() })
      }
      const entry = byStore.get(row.store_id)!
      entry.values.set(period, (entry.values.get(period) ?? 0) + row.total_sales_amount)
    })

    const periods = Array.from(periodSet).sort()
    const series: TrendSeriesData[] = Array.from(byStore.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([storeId, info]) => ({
        id: storeId,
        label: info.name,
        colorVar: storeColor.get(storeId) ?? 'var(--text-muted)',
        points: periods.map((period) => ({ period, value: info.values.get(period) ?? 0 })),
      }))

    return { periods, series }
  }, [filtered, storeColor])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>日別店舗別売上</h2>
        <div className="view-toggle" role="tablist" aria-label="表示切り替え">
          <button aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
            グラフ
          </button>
          <button aria-pressed={view === 'table'} onClick={() => setView('table')}>
            表
          </button>
        </div>
      </div>
      {view === 'chart' && (
        <p className="panel-subtitle">月次集計の推移（表は日次明細）。売上低下の傾向を早期に把握する目的で表示</p>
      )}

      <div className="filter-row">
        <label htmlFor="store-filter">店舗:</label>
        <select
          id="store-filter"
          value={storeFilter}
          onChange={(e) => setStoreFilter(e.target.value)}
        >
          <option value="all">すべて</option>
          {stores.map((store) => (
            <option key={store.id} value={store.id}>
              {store.name}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="error-state">{error}</p>}
      {!error && !data && <p className="empty-state">読み込み中...</p>}
      {!error && data && filtered.length === 0 && (
        <p className="empty-state">データがありません</p>
      )}

      {!error && filtered.length > 0 && view === 'chart' && (
        <TrendChart
          periods={trend.periods}
          series={trend.series}
          valueFormatter={(v) => `¥${v.toLocaleString('ja-JP')}`}
        />
      )}

      {!error && filtered.length > 0 && view === 'table' && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>日付</th>
                <th>店舗名</th>
                <th>地域</th>
                <th>取引件数</th>
                <th>数量</th>
                <th>売上金額</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={`${row.sales_date}-${row.store_id}`}>
                  <td>{row.sales_date}</td>
                  <td>{row.store_name}</td>
                  <td>{row.region}</td>
                  <td>{row.transaction_count.toLocaleString('ja-JP')}</td>
                  <td>{row.total_quantity.toLocaleString('ja-JP')}</td>
                  <td>¥{row.total_sales_amount.toLocaleString('ja-JP')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
