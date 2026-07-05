import { useState } from 'react';
import { fetchCategorySales, fetchStoreRanking } from '../api/client';
import { FilterBar } from '../components/FilterBar';
import { CategorySalesChart } from '../components/charts/CategorySalesChart';
import { useAsync } from '../hooks/useAsync';
import { useStoreOptions } from '../hooks/useStoreOptions';
import { formatCurrency } from '../format';
import styles from './ProductPlanningView.module.css';

/** 商品企画ビュー: カテゴリ別売上構成と店舗ランキング。 */
export function ProductPlanningView() {
  const { options: storeOptions } = useStoreOptions();
  const [storeIds, setStoreIds] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const storeId = storeIds.join(',') || undefined;
  const filters = { storeId, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined };

  const categories = useAsync(() => fetchCategorySales(filters), [storeId, dateFrom, dateTo]);
  const ranking = useAsync(() => fetchStoreRanking(filters), [storeId, dateFrom, dateTo]);

  return (
    <div>
      <FilterBar
        storeOptions={storeOptions}
        selectedStoreIds={storeIds}
        onStoreIdsChange={setStoreIds}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      <div className={styles.grid}>
        <div className={styles.card}>
          <h3>カテゴリ別売上構成</h3>
          {categories.error && <p role="alert">取得に失敗しました: {categories.error}</p>}
          {categories.data && <CategorySalesChart data={categories.data} />}
        </div>

        <div className={styles.card}>
          <h3>店舗ランキング</h3>
          {ranking.error && <p role="alert">取得に失敗しました: {ranking.error}</p>}
          {ranking.data && (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>順位</th>
                  <th>店舗</th>
                  <th>Net Sales</th>
                </tr>
              </thead>
              <tbody>
                {ranking.data.map((row) => (
                  <tr key={row.store_id}>
                    <td>
                      <span className={styles.rankBadge}>{row.rank}</span>
                    </td>
                    <td>{row.store_name}</td>
                    <td>{formatCurrency(row.net_sales)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
