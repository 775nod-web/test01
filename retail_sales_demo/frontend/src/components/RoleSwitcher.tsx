import type { Role } from '../types';
import styles from './RoleSwitcher.module.css';

const ROLES: { value: Role; label: string }[] = [
  { value: 'hq', label: '本社経営ダッシュボード' },
  { value: 'store', label: '店舗ビュー' },
  { value: 'product-planning', label: '商品企画ビュー' },
  { value: 'data-quality', label: 'データ品質ビュー' },
];

interface Props {
  role: Role;
  onChange: (role: Role) => void;
}

/**
 * Demo-only role switcher. This selector is a UI convenience for showing all
 * four screens from one build — it does NOT enforce access control. Actual
 * row/store-level access control must be enforced server-side (Unity
 * Catalog grants and/or the API layer in Phase 3); switching this selector
 * never grants access to data the API wouldn't otherwise return.
 */
export function RoleSwitcher({ role, onChange }: Props) {
  return (
    <div className={styles.wrapper}>
      <span className={styles.label}>表示ロール切替（デモ用）</span>
      <div className={styles.options}>
        {ROLES.map((r) => (
          <button
            key={r.value}
            type="button"
            className={r.value === role ? styles.active : styles.option}
            onClick={() => onChange(r.value)}
          >
            {r.label}
          </button>
        ))}
      </div>
      <p className={styles.disclaimer}>
        このセレクタは画面の見せ方を切り替えるだけのデモ用UIです。実際のアクセス制御はサーバー側
        （Unity Catalog / API）で行われます。
      </p>
    </div>
  );
}
