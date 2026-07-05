import { fetchAlerts } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import styles from './AlertBanner.module.css';

const COMPARISON_LABEL: Record<string, string> = { DoD: '前日比', WoW: '前週比' };

/**
 * Phase 3-D: reads GET /api/alerts, which serves the latest day's rows from
 * gold_store_sales_alerts — written by the daily batch job
 * (jobs/alert_batch.py). That job has not been deployed/run from this
 * session (no Databricks workspace access), so an empty/error state here may
 * just mean the batch hasn't produced data yet, not that stores are healthy.
 */
export function AlertBanner() {
  const { data, error, loading } = useAsync(() => fetchAlerts(), []);

  if (loading) return null;

  if (error) {
    return (
      <div className={`${styles.wrapper} ${styles.empty}`}>
        売上急減アラートの取得に失敗しました: {error}
        <p className={styles.note}>
          gold_store_sales_alerts が未作成の可能性があります（jobs/alert_batch.py はまだ本番デプロイされていません）。
        </p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={`${styles.wrapper} ${styles.empty}`}>
        現在、売上急減アラートはありません。
        <p className={styles.note}>
          gold_store_sales_alerts（jobs/alert_batch.pyが日次で書き込み）の最新日分を表示しています。
        </p>
      </div>
    );
  }

  return (
    <div className={`${styles.wrapper} ${styles.active}`}>
      <p className={styles.title}>売上急減アラート（{data.length}件）</p>
      <ul className={styles.list}>
        {data.map((a) => (
          <li key={`${a.store_id}-${a.comparison_type}`}>
            {a.store_name}: {COMPARISON_LABEL[a.comparison_type] ?? a.comparison_type} {a.pct_change.toFixed(1)}%
            （しきい値 {a.threshold_pct}%）
          </li>
        ))}
      </ul>
    </div>
  );
}
