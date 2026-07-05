import { useEffect, useState } from 'react';
import { fetchDailyStoreSales, fetchKpiSummary } from '../api/client';
import { FilterBar } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { DailyStoreSalesChart } from '../components/charts/DailyStoreSalesChart';
import { useAsync } from '../hooks/useAsync';
import { useStoreOptions } from '../hooks/useStoreOptions';
import { formatCurrency, formatNumber } from '../format';
import styles from './StoreView.module.css';

/**
 * 店舗ビュー: ログインした店長は自店舗のデータしか見えない想定の画面。
 *
 * Phase 3で店舗別アクセス制御（どのユーザーがどの店舗を担当するか）が実装されるまで、
 * このセッションはどの店舗のログインユーザーであるかをサーバー側で判定できない。そのため
 * 下の「ログインシミュレーション」セレクタで店舗を選ばせているが、これはデモ限定の代替UIであり、
 * 本番では店舗選択UIごと廃止し、ログインユーザーに紐づく store_id をサーバー側（API/Unity
 * Catalog側の行レベルセキュリティ）で強制する。フロントエンドは store_id をAPIパラメータとして
 * 渡す口だけを用意しておけばよく、その配線は既にここで完了している。
 */
export function StoreView() {
  const { options: storeOptions } = useStoreOptions();
  const [simulatedStoreId, setSimulatedStoreId] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  useEffect(() => {
    if (!simulatedStoreId && storeOptions.length > 0) {
      setSimulatedStoreId(storeOptions[0].storeId);
    }
  }, [storeOptions, simulatedStoreId]);

  const filters = {
    storeId: simulatedStoreId || undefined,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
  };
  const kpiState = useAsync(() => fetchKpiSummary(filters), [simulatedStoreId, dateFrom, dateTo]);
  const dailyState = useAsync(() => fetchDailyStoreSales(filters), [simulatedStoreId, dateFrom, dateTo]);
  const kpi = kpiState.data;

  return (
    <div>
      <div className={styles.loginSim}>
        ログインシミュレーション（デモ用。本番ではPhase 3のアクセス制御でサーバー側から自動決定）:
        <select value={simulatedStoreId} onChange={(e) => setSimulatedStoreId(e.target.value)}>
          {storeOptions.map((s) => (
            <option key={s.storeId} value={s.storeId}>
              {s.storeName}
            </option>
          ))}
        </select>
      </div>

      <FilterBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      {kpiState.error && <p role="alert">KPIサマリーの取得に失敗しました: {kpiState.error}</p>}

      <div className={styles.kpiRow}>
        <KpiCard label="Net Sales" value={kpi ? formatCurrency(kpi.net_sales) : '—'} />
        <KpiCard
          label="Gross Sales"
          value={kpi ? formatCurrency(kpi.gross_sales) : '—'}
          estimated={kpi?.gross_sales_is_estimated}
          estimatedNote={kpi?.gross_sales_note}
        />
        <KpiCard label="Transaction Count" value={kpi ? formatNumber(kpi.transaction_count) : '—'} />
        <KpiCard label="Units Sold" value={kpi ? formatNumber(kpi.units_sold) : '—'} />
        <KpiCard
          label="Average Basket Size"
          value={kpi?.average_basket_size != null ? formatCurrency(kpi.average_basket_size) : '—'}
        />
      </div>

      <div className={styles.chartCard}>
        <h3>自店舗 売上推移</h3>
        {dailyState.error && <p role="alert">売上推移の取得に失敗しました: {dailyState.error}</p>}
        {dailyState.data && <DailyStoreSalesChart data={dailyState.data} />}
      </div>
    </div>
  );
}
