import type {
  CategorySales,
  DailyStoreSales,
  StoreRanking,
  UnregisteredMasterReportRow,
} from './types'

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`${path} が失敗しました (HTTP ${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  dailyStoreSales: () => getJson<DailyStoreSales[]>('/api/daily-store-sales'),
  categorySales: () => getJson<CategorySales[]>('/api/category-sales'),
  storeRanking: () => getJson<StoreRanking[]>('/api/store-ranking'),
  unregisteredMasterReport: () =>
    getJson<UnregisteredMasterReportRow[]>('/api/unregistered-master-report'),
}
