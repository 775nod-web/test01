import { useState } from 'react';
import { fetchDailyStoreSales, fetchKpiSummary, fetchMe } from '../api/client';
import { FilterBar } from '../components/FilterBar';
import { KpiCard } from '../components/KpiCard';
import { DailyStoreSalesChart } from '../components/charts/DailyStoreSalesChart';
import { DEMO_IDENTITIES } from '../demoIdentities';
import { useAsync } from '../hooks/useAsync';
import { formatCurrency, formatNumber } from '../format';
import styles from './StoreView.module.css';

/**
 * 店舗ビュー: ログインした店長は自店舗のデータしか見えない想定の画面。
 *
 * Phase 3で店舗別アクセス制御を実装したが、実在のログイン/SSOがこのセッションには無いため、
 * 下の「ログインシミュレーション」セレクタで X-Forwarded-Email ヘッダーを切り替えている
 * （本番のDatabricks Appsが行うはずのユーザー転送を模した、デモ限定の代替UI — 詳細は
 * demoIdentities.ts と docs/phase3_governance_and_ops.md を参照）。
 *
 * 重要: ここでは store_id をクエリパラメータとして渡していない。サーバー側
 * （app/backend/access_control.py）がこのヘッダーの user_email から許可店舗を解決し、
 * 何も指定しなければ許可された店舗だけが返る。つまり実店舗の絞り込みはサーバー側で
 * 強制されており、フロントエンドが信頼されているわけではない。
 */
export function StoreView() {
  const [asUser, setAsUser] = useState(DEMO_IDENTITIES[2].email); // default: store1 manager
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const me = useAsync(() => fetchMe(asUser), [asUser]);

  const filters = { asUser, dateFrom: dateFrom || undefined, dateTo: dateTo || undefined };
  const kpiState = useAsync(() => fetchKpiSummary(filters), [asUser, dateFrom, dateTo]);
  const dailyState = useAsync(() => fetchDailyStoreSales(filters), [asUser, dateFrom, dateTo]);
  const kpi = kpiState.data;

  return (
    <div>
      <div className={styles.loginSim}>
        ログインシミュレーション（デモ用。本番ではSSOでサーバー側から自動決定）:
        <select value={asUser} onChange={(e) => setAsUser(e.target.value)}>
          {DEMO_IDENTITIES.map((id) => (
            <option key={id.email} value={id.email}>
              {id.label}
            </option>
          ))}
        </select>
        {me.data && (
          <span>
            {' '}
            → 許可店舗:{' '}
            {me.data.allowed_store_ids === null ? '全店舗' : me.data.allowed_store_ids.join(', ') || 'なし'}
          </span>
        )}
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
