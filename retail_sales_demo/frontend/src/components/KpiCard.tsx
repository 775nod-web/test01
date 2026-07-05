import styles from './KpiCard.module.css';

interface Props {
  label: string;
  value: string;
  /** % change vs. the previous period, when a comparison was requested. */
  deltaPct?: number | null;
  estimated?: boolean;
  estimatedNote?: string;
}

export function KpiCard({ label, value, deltaPct, estimated, estimatedNote }: Props) {
  const [bg, fg] =
    deltaPct == null || deltaPct === 0
      ? ['var(--pastel-blue)', 'var(--pastel-blue-text)']
      : deltaPct > 0
        ? ['var(--pastel-green)', 'var(--pastel-green-text)']
        : ['var(--pastel-coral)', 'var(--pastel-coral-text)'];

  return (
    <div className={styles.card} style={{ background: bg, color: fg }}>
      <p className={styles.label}>{label}</p>
      <p className={styles.value}>{value}</p>
      <div className={styles.footer}>
        {deltaPct != null && (
          <span className={styles.delta}>
            {deltaPct > 0 ? '+' : ''}
            {deltaPct.toFixed(1)}% (前期間比)
          </span>
        )}
        {estimated && (
          <span className={styles.badge} title={estimatedNote}>
            暫定値
          </span>
        )}
      </div>
    </div>
  );
}
