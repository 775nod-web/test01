import { useEffect, useState } from 'react'
import { api } from './api'
import type { StoreRanking, UnregisteredMasterReportRow } from './types'
import { StatTile } from './components/StatTile'
import { CategorySalesPanel } from './components/CategorySalesPanel'
import { StoreRankingPanel } from './components/StoreRankingPanel'
import { DailyStoreSalesPanel } from './components/DailyStoreSalesPanel'
import { UnregisteredMasterReportPanel } from './components/UnregisteredMasterReportPanel'

type Theme = 'light' | 'dark'

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = window.localStorage.getItem('theme')
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('theme', theme)
  }, [theme])

  return [theme, () => setTheme((t) => (t === 'light' ? 'dark' : 'light'))]
}

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [ranking, setRanking] = useState<StoreRanking[] | null>(null)
  const [unregistered, setUnregistered] = useState<UnregisteredMasterReportRow[] | null>(null)

  useEffect(() => {
    api.storeRanking().then(setRanking).catch(() => setRanking([]))
    api.unregisteredMasterReport().then(setUnregistered).catch(() => setUnregistered([]))
  }, [])

  const totalSales = ranking?.reduce((sum, row) => sum + row.total_sales_amount, 0) ?? null
  const totalTransactions = ranking?.reduce((sum, row) => sum + row.transaction_count, 0) ?? null
  const storeCount = ranking?.length ?? null
  const unregisteredCount = unregistered?.length ?? null

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>小売売上ダッシュボード</h1>
          <p>Gold layer（gold_daily_store_sales / gold_category_sales / gold_store_ranking / gold_unregistered_master_report）を配信</p>
        </div>
        <button className="theme-toggle" onClick={toggleTheme}>
          {theme === 'light' ? '🌙 ダーク' : '☀️ ライト'}
        </button>
      </header>

      <div className="kpi-row">
        <StatTile
          label="総売上金額"
          value={totalSales != null ? `¥${totalSales.toLocaleString('ja-JP')}` : '—'}
        />
        <StatTile
          label="総取引件数"
          value={totalTransactions != null ? totalTransactions.toLocaleString('ja-JP') : '—'}
        />
        <StatTile label="店舗数" value={storeCount != null ? `${storeCount}店舗` : '—'} />
        <StatTile
          label="マスター未登録取引"
          value={unregisteredCount != null ? `${unregisteredCount}件` : '—'}
          note="要フォローアップ"
          status={unregisteredCount ? 'warning' : undefined}
        />
      </div>

      <StoreRankingPanel />
      <CategorySalesPanel />
      <DailyStoreSalesPanel />
      <UnregisteredMasterReportPanel />
    </div>
  )
}
