import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CategorySales } from '../types'
import { BarChart } from './BarChart'

// カテゴリ配色は出現順でslot 1から固定割り当て（循環させない。
// 7スロットを超えた場合はtext-mutedにフォールドする）
const SERIES_VARS = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
  'var(--series-5)', 'var(--series-6)', 'var(--series-7)',
]

export function CategorySalesPanel() {
  const [data, setData] = useState<CategorySales[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.categorySales().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>商品カテゴリ別売上</h2>
      </div>
      {error && <p className="error-state">{error}</p>}
      {!error && !data && <p className="empty-state">読み込み中...</p>}
      {!error && data && data.length === 0 && <p className="empty-state">データがありません</p>}
      {!error && data && data.length > 0 && (
        <BarChart
          data={data.map((row, index) => ({
            label: `${row.category}（商品数 ${row.product_count}）`,
            value: row.total_sales_amount,
            colorVar: SERIES_VARS[index] ?? 'var(--text-muted)',
          }))}
          valueFormatter={(v) => `¥${v.toLocaleString('ja-JP')}`}
        />
      )}
    </section>
  )
}
