import type { ReactNode } from 'react';
import styles from './Phase3Placeholder.module.css';

interface Props {
  title: string;
  description: string;
  children?: ReactNode;
}

/**
 * Reserves layout space for a Phase 3 feature (alert API, quarantine-rate
 * trend, re-match job trigger) that isn't implemented yet. Renders a clearly
 * marked "未実装" placeholder instead of a dummy chart/button that could be
 * mistaken for live data.
 */
export function Phase3Placeholder({ title, description, children }: Props) {
  return (
    <div className={styles.box}>
      <span className={styles.tag}>Phase 3 未実装</span>
      <span className={styles.title}>{title}</span>
      <p>{description}</p>
      {children}
    </div>
  );
}
