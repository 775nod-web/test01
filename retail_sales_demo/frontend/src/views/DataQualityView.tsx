import { useState } from 'react';
import { fetchQuarantineReport, fetchRequeueStatus } from '../api/client';
import { AuditLogPanel } from '../components/AuditLogPanel';
import { FilterBar } from '../components/FilterBar';
import { Phase3Placeholder } from '../components/Phase3Placeholder';
import { RequeueButton } from '../components/RequeueButton';
import { DEMO_IDENTITIES } from '../demoIdentities';
import { useAsync } from '../hooks/useAsync';
import { useIssueTypeOptions } from '../hooks/useIssueTypeOptions';
import { useStoreOptions } from '../hooks/useStoreOptions';
import styles from './DataQualityView.module.css';

/** データ品質ビュー: マスター未登録レポート(PIIマスキング付き)、再照合トリガー、監査ログ。 */
export function DataQualityView() {
  const { options: storeOptions } = useStoreOptions();
  const issueTypeOptions = useIssueTypeOptions();
  const [storeIds, setStoreIds] = useState<string[]>([]);
  const [issueType, setIssueType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [asUser, setAsUser] = useState(DEMO_IDENTITIES[1].email); // default: dq-demo (PII_VIEWER + AUDIT_VIEWER)
  const [requeueRefreshKey, setRequeueRefreshKey] = useState(0);

  const storeId = storeIds.join(',') || undefined;
  const report = useAsync(
    () =>
      fetchQuarantineReport({
        storeId,
        issueType: issueType || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        asUser,
      }),
    [storeId, issueType, dateFrom, dateTo, asUser],
  );
  const requeueStatus = useAsync(() => fetchRequeueStatus(), [requeueRefreshKey]);

  return (
    <div>
      <label className={styles.issueFilter}>
        実行ユーザー（デモ用、PIIマスキング・監査ログ閲覧権限のロールが変わります）
        <select value={asUser} onChange={(e) => setAsUser(e.target.value)}>
          {DEMO_IDENTITIES.map((id) => (
            <option key={id.email} value={id.email}>
              {id.label}
            </option>
          ))}
        </select>
      </label>

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
        description="発生率の時系列推移はまだ実装していません。再照合バッチ(jobs/requeue_batch.py)は直近実行のスナップショット（件数）のみを記録します。"
      />

      <div className={styles.actions}>
        <RequeueButton onTriggered={() => setRequeueRefreshKey((k) => k + 1)} />
      </div>

      {requeueStatus.data?.run_id == null ? (
        <p className={styles.issueFilter}>再照合バッチはまだ一度も実行されていません。</p>
      ) : (
        <p className={styles.issueFilter}>
          直近の再照合実行: {requeueStatus.data.started_at} / ステータス: {requeueStatus.data.status} /
          チェック件数: {requeueStatus.data.records_checked} / 再照合候補: {requeueStatus.data.reconciled_candidates_found}
        </p>
      )}

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
                <th>顧客ID</th>
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
                    {row.customer_id ?? '—'}
                    {row.customer_id_is_masked && (
                      <span className={styles.issueBadge} title="PII_VIEWERロールが無いためマスク表示">
                        マスク済み
                      </span>
                    )}
                  </td>
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

      <AuditLogPanel asUser={asUser} />
    </div>
  );
}
