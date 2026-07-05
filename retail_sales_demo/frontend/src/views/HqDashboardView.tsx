import { useState } from 'react';
import { fetchDailyStoreSales, fetchKpiSummary } from '../api/client';
import { FilterBar } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { Phase3Placeholder } from '../components/Phase3Placeholder';
import { DailyStoreSalesChart } from '../components/charts/DailyStoreSalesChart';
import { useAsync } from '../hooks/useAsync';
import { useStoreOptions } from '../hooks/useStoreOptions';
import { formatCurrency, formatNumber, pctDelta, previousPeriod } from '../format';
import styles from './HqDashboardView.module.css';

/** 本社経営ダッシュボード: KPIサマリー、日別×店舗の売上推移、売上急減アラート（枠のみ）。 */
export function HqDashboardView() {
  const { options: storeOptions } = useStoreOptions();
  const [storeIds, setStoreIds] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [compareEnabled, setCompareEnabled] = useState(false);

  const storeId = storeIds.join(',') || undefined;
  const filters = { storeId, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined };

  const current = useAsync(() => fetchKpiSummary(filters), [storeId, dateFrom, dateTo]);

  const canCompare = compareEnabled && !!dateFrom && !!dateTo;
  const prevRange = canCompare ? previousPeriod(dateFrom, dateTo) : null;
  const previous = useAsync(
    () =>
      prevRange
        ? fetchKpiSummary({ storeId, dateFrom: prevRange.from, dateTo: prevRange.to })
        : Promise.resolve(null),
    [canCompare, prevRange?.from, prevRange?.to, storeId],
  );

  const kpi = current.data;
  const prevKpi = previous.data;

  const daily = useAsync(() => fetchDailyStoreSales(filters), [storeId, dateFrom, dateTo]);

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
        compareEnabled={compareEnabled}
        onCompareEnabledChange={setCompareEnabled}
      />

      <Phase3Placeholder
        title="売上急減アラート"
        description="店舗別の売上急減を検知するアラートAPI（Phase 3実装予定）に接続する枠です。現時点ではダミー表示です。"
      />

      {current.error && <p role="alert">KPIサマリーの取得に失敗しました: {current.error}</p>}

      <div className={styles.kpiRow}>
        <KpiCard
          label="Net Sales"
          value={kpi ? formatCurrency(kpi.net_sales) : '—'}
          deltaPct={prevKpi ? pctDelta(kpi!.net_sales, prevKpi.net_sales) : null}
        />
        <KpiCard
          label="Gross Sales"
          value={kpi ? formatCurrency(kpi.gross_sales) : '—'}
          deltaPct={prevKpi ? pctDelta(kpi!.gross_sales, prevKpi.gross_sales) : null}
          estimated={kpi?.gross_sales_is_estimated}
          estimatedNote={kpi?.gross_sales_note}
        />
        <KpiCard
          label="Transaction Count"
          value={kpi ? formatNumber(kpi.transaction_count) : '—'}
          deltaPct={prevKpi ? pctDelta(kpi!.transaction_count, prevKpi.transaction_count) : null}
        />
        <KpiCard
          label="Units Sold"
          value={kpi ? formatNumber(kpi.units_sold) : '—'}
          deltaPct={prevKpi ? pctDelta(kpi!.units_sold, prevKpi.units_sold) : null}
        />
        <KpiCard
          label="Average Basket Size"
          value={kpi?.average_basket_size != null ? formatCurrency(kpi.average_basket_size) : '—'}
          deltaPct={
            prevKpi && kpi?.average_basket_size != null
              ? pctDelta(kpi.average_basket_size, prevKpi.average_basket_size)
              : null
          }
        />
      </div>

      <div className={styles.chartCard}>
        <h3 className={styles.chartTitle}>日別×店舗 売上推移</h3>
        {daily.error && <p role="alert">売上推移の取得に失敗しました: {daily.error}</p>}
        {daily.data && <DailyStoreSalesChart data={daily.data} />}
      </div>
    </div>
  );
}
