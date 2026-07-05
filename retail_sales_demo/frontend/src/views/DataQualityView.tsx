import { useState } from 'react';
import { fetchQuarantineReport } from '../api/client';
import { FilterBar } from '../components/FilterBar';
import { Phase3Placeholder } from '../components/Phase3Placeholder';
import { RequeueButton } from '../components/RequeueButton';
import { useAsync } from '../hooks/useAsync';
import { useIssueTypeOptions } from '../hooks/useIssueTypeOptions';
import { useStoreOptions } from '../hooks/useStoreOptions';
import styles from './DataQualityView.module.css';

/** データ品質ビュー: マスター未登録レポート、quarantine率推移（枠のみ）、再照合トリガー（ダミー）。 */
export function DataQualityView() {
  const { options: storeOptions } = useStoreOptions();
  const issueTypeOptions = useIssueTypeOptions();
  const [storeIds, setStoreIds] = useState<string[]>([]);
  const [issueType, setIssueType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const storeId = storeIds.join(',') || undefined;
  const report = useAsync(
    () =>
      fetchQuarantineReport({
        storeId,
        issueType: issueType || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
    [storeId, issueType, dateFrom, dateTo],
  );

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

      <label className={styles.issueFilter}>
        issue_type で絞り込み
        <select value={issueType} onChange={(e) => setIssueType(e.target.value)}>
          <option value="">すべて</option>
          {issueTypeOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <Phase3Placeholder
        title="quarantine率推移"
        description="マスター未登録取引の発生率の時系列推移（Phase 3実装予定）。現時点ではダミー表示です。"
      />

      <div className={styles.actions}>
        <RequeueButton />
      </div>

      <div className={styles.card}>
        <h3>マスター未登録レポート</h3>
        {report.error && <p role="alert">取得に失敗しました: {report.error}</p>}
        {report.data && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>取引日</th>
                <th>取引ID</th>
                <th>店舗ID</th>
                <th>商品ID</th>
                <th>issue_type</th>
                <th>金額</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              {report.data.map((row) => (
                <tr key={row.transaction_id}>
                  <td>{row.transaction_date}</td>
                  <td>{row.transaction_id}</td>
                  <td>{row.store_id ?? '—'}</td>
                  <td>{row.product_id ?? '—'}</td>
                  <td>
                    <span className={styles.issueBadge}>{row.issue_type}</span>
                  </td>
                  <td>{row.net_sales ?? '—'}</td>
                  <td>{row.quantity ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
