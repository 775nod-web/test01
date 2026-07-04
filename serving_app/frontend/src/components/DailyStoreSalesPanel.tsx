import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { DailyStoreSales } from '../types'

export function DailyStoreSalesPanel() {
  const [data, setData] = useState<DailyStoreSales[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [storeFilter, setStoreFilter] = useState<string>('all')

  useEffect(() => {
    api.dailyStoreSales().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  const stores = useMemo(() => {
    if (!data) return [] as Array<[string, string]>
    const seen = new Map<string, string>()
    data.forEach((row) => seen.set(row.store_id, row.store_name))
    return Array.from(seen.entries())
  }, [data])

  const filtered = useMemo(() => {
    if (!data) return []
    if (storeFilter === 'all') return data
    return data.filter((row) => row.store_id === storeFilter)
  }, [data, storeFilter])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>日別店舗別売上</h2>
      </div>

      {/* フィルタは表の上の1行にまとめる */}
      <div className="filter-row">
        <label htmlFor="store-filter">店舗:</label>
        <select
          id="store-filter"
          value={storeFilter}
          onChange={(e) => setStoreFilter(e.target.value)}
        >
          <option value="all">すべて</option>
          {stores.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="error-state">{error}</p>}
      {!error && !data && <p className="empty-state">読み込み中...</p>}
      {!error && data && filtered.length === 0 && (
        <p className="empty-state">データがありません</p>
      )}

      {!error && filtered.length > 0 && (
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
