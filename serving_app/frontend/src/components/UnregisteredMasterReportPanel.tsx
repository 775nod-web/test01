import { useEffect, useState } from 'react'
import { api } from '../api'
import type { UnregisteredMasterReportRow } from '../types'

// 状態色（good/warning/serious/critical）はカテゴリ配色とは別枠で固定。
// アイコン＋ラベルを必ず併記し、色だけで意味を伝えない。
function IssueBadge({ issueType }: { issueType: string }) {
  const isBothMissing = issueType.includes(',')
  return (
    <span className={`badge ${isBothMissing ? 'badge-critical' : 'badge-warning'}`}>
      {isBothMissing ? '⛔' : '⚠️'} {issueType}
    </span>
  )
}

function formatYen(value: number | null): string {
  return value != null ? `¥${value.toLocaleString('ja-JP')}` : '—'
}

export function UnregisteredMasterReportPanel() {
  const [data, setData] = useState<UnregisteredMasterReportRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.unregisteredMasterReport().then(setData).catch((e: Error) => setError(e.message))
  }, [])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>マスター未登録レポート</h2>
      </div>
      {error && <p className="error-state">{error}</p>}
      {!error && !data && <p className="empty-state">読み込み中...</p>}
      {!error && data && data.length === 0 && (
        <p className="empty-state">未登録の取引はありません</p>
      )}
      {!error && data && data.length > 0 && (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>取引ID</th>
                <th>課題種別</th>
                <th>店舗ID</th>
                <th>商品ID</th>
                <th>顧客ID</th>
                <th>取引日時</th>
                <th>数量</th>
                <th>単価</th>
                <th>割引額</th>
                <th>売上金額</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.transaction_id}>
                  <td>{row.transaction_id}</td>
                  <td>
                    <IssueBadge issueType={row.issue_type} />
                  </td>
                  <td>{row.store_id ?? '—'}</td>
                  <td>{row.product_id ?? '—'}</td>
                  <td>{row.customer_id ?? '—'}</td>
                  <td>{row.transaction_datetime ?? '—'}</td>
                  <td>{row.quantity ?? '—'}</td>
                  <td>{formatYen(row.unit_price)}</td>
                  <td>{formatYen(row.discount_amount)}</td>
                  <td>{formatYen(row.sales_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
