import { useEffect, useState } from 'react'
import { api } from '../api'
import type { StoreRanking } from '../types'
import { BarChart } from './BarChart'

const SERIES_VARS = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)',
]

export function StoreRankingPanel() {
  const [data, setData] = useState<StoreRanking[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'chart' | 'table'>('chart')

  useEffect(() => {
    api.storeRanking().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>店舗ランキング（売上金額順）</h2>
        <div className="view-toggle" role="tablist" aria-label="表示切り替え">
          <button aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
            グラフ
          </button>
          <button aria-pressed={view === 'table'} onClick={() => setView('table')}>
            表
          </button>
        </div>
      </div>
      {error && <p className="error-state">{error}</p>}
      {!error && !data && <p className="empty-state">読み込み中...</p>}
      {!error && data && data.length === 0 && <p className="empty-state">データがありません</p>}

      {!error && data && data.length > 0 && view === 'chart' && (
        <BarChart
          data={data.map((row) => ({
            label: `${row.sales_rank}位 ${row.store_name}`,
            value: row.total_sales_amount,
            colorVar: SERIES_VARS[row.sales_rank - 1] ?? 'var(--text-muted)',
          }))}
          valueFormatter={(v) => `¥${v.toLocaleString('ja-JP')}`}
        />
      )}

      {!error && data && data.length > 0 && view === 'table' && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>順位</th>
                <th>店舗名</th>
                <th>地域</th>
                <th>店舗タイプ</th>
                <th>売上金額</th>
                <th>数量</th>
                <th>取引件数</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.store_id}>
                  <td>{row.sales_rank}</td>
                  <td>{row.store_name}</td>
                  <td>{row.region}</td>
                  <td>{row.store_type}</td>
                  <td>¥{row.total_sales_amount.toLocaleString('ja-JP')}</td>
                  <td>{row.total_quantity.toLocaleString('ja-JP')}</td>
                  <td>{row.transaction_count.toLocaleString('ja-JP')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
