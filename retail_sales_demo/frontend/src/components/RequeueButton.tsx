import { useState } from 'react';
import styles from './RequeueButton.module.css';

/**
 * Dummy "re-match" trigger. Phase 3 is expected to wire this to a real job
 * trigger API (e.g. a Databricks Jobs run); until then, clicking it only
 * simulates a call so the UI flow can be demoed end-to-end.
 */
export function RequeueButton() {
  const [status, setStatus] = useState<'idle' | 'running' | 'done'>('idle');

  const handleClick = () => {
    setStatus('running');
    window.setTimeout(() => setStatus('done'), 800);
  };

  return (
    <div>
      <button
        type="button"
        className={styles.button}
        onClick={handleClick}
        disabled={status === 'running'}
      >
        再照合を実行
      </button>
      {status === 'running' && <span className={styles.status}>実行中（ダミー）...</span>}
      {status === 'done' && (
        <span className={styles.status}>
          ダミー動作です。Phase 3のジョブトリガーAPIが未実装のため実際の再照合は行われていません。
        </span>
      )}
    </div>
  );
}
