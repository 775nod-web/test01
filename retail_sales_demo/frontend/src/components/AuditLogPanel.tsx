import { fetchAuditLog } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import styles from './AuditLogPanel.module.css';

interface Props {
  asUser: string;
}

/**
 * Phase 3-C fallback audit log viewer. Reads GET /api/audit-log, which is
 * gated to AUDIT_VIEWER/admin identities server-side (access_control.py) —
 * a 403 here is the server enforcing that, not a frontend bug.
 */
export function AuditLogPanel({ asUser }: Props) {
  const { data, error, loading } = useAsync(() => fetchAuditLog(200, asUser), [asUser]);

  return (
    <div className={styles.card}>
      <h3>監査ログ（直近200件）</h3>
      {loading && <p className={styles.denied}>読み込み中...</p>}
      {error && <p className={styles.denied}>{error}</p>}
      {data && data.length === 0 && <p className={styles.denied}>ログがまだありません。</p>}
      {data && data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>日時</th>
              <th>ユーザー</th>
              <th>エンドポイント</th>
              <th>store_idフィルタ</th>
              <th>ステータス</th>
            </tr>
          </thead>
          <tbody>
            {data.map((entry, i) => (
              <tr key={i}>
                <td>{entry.logged_at}</td>
                <td>{entry.user_email}</td>
                <td>{entry.endpoint}</td>
                <td>{entry.store_id_filter ?? '—'}</td>
                <td className={entry.status_code < 400 ? styles.statusOk : styles.statusErr}>
                  {entry.status_code}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
