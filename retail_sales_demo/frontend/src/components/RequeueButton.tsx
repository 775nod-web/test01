import { useState } from 'react';
import { triggerRequeueJob } from '../api/client';
import styles from './RequeueButton.module.css';

/**
 * Phase 3-E: triggers jobs/requeue_batch.py via POST /api/requeue-trigger
 * (Databricks Jobs API run-now). That job has not been deployed to a live
 * workspace from this session, so the backend currently returns HTTP 501
 * with a clear message rather than pretending to succeed — this component
 * just surfaces whatever the backend says instead of hiding it.
 */
export function RequeueButton({ onTriggered }: { onTriggered?: () => void }) {
  const [state, setState] = useState<{ status: 'idle' | 'running' | 'done' | 'error'; message?: string }>({
    status: 'idle',
  });

  const handleClick = async () => {
    setState({ status: 'running' });
    try {
      const result = await triggerRequeueJob();
      setState({ status: 'done', message: `${result.message}（run_id: ${result.run_id}）` });
      onTriggered?.();
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : String(err) });
    }
  };

  return (
    <div>
      <button
        type="button"
        className={styles.button}
        onClick={handleClick}
        disabled={state.status === 'running'}
      >
        再照合を実行
      </button>
      {state.status === 'running' && <span className={styles.status}>実行中...</span>}
      {state.status === 'done' && <span className={styles.status}>{state.message}</span>}
      {state.status === 'error' && <span className={styles.status}>{state.message}</span>}
    </div>
  );
}
