import type { StoreOption } from '../hooks/useStoreOptions';
import styles from './FilterBar.module.css';

interface Props {
  storeOptions?: StoreOption[];
  selectedStoreIds?: string[];
  onStoreIdsChange?: (storeIds: string[]) => void;
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  compareEnabled?: boolean;
  onCompareEnabledChange?: (value: boolean) => void;
}

export function FilterBar({
  storeOptions,
  selectedStoreIds,
  onStoreIdsChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  compareEnabled,
  onCompareEnabledChange,
}: Props) {
  return (
    <div className={styles.bar}>
      {storeOptions && onStoreIdsChange && (
        <label className={styles.field}>
          店舗（複数選択可、未選択で全店舗）
          <select
            multiple
            value={selectedStoreIds ?? []}
            onChange={(e) =>
              onStoreIdsChange(Array.from(e.target.selectedOptions, (o) => o.value))
            }
            size={Math.min(4, Math.max(2, storeOptions.length))}
          >
            {storeOptions.map((s) => (
              <option key={s.storeId} value={s.storeId}>
                {s.storeName}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className={styles.field}>
        期間（開始）
        <input type="date" value={dateFrom} onChange={(e) => onDateFromChange(e.target.value)} />
      </label>
      <label className={styles.field}>
        期間（終了）
        <input type="date" value={dateTo} onChange={(e) => onDateToChange(e.target.value)} />
      </label>
      {onCompareEnabledChange && (
        <label className={styles.checkboxField}>
          <input
            type="checkbox"
            checked={compareEnabled ?? false}
            disabled={!dateFrom || !dateTo}
            onChange={(e) => onCompareEnabledChange(e.target.checked)}
          />
          前期間と比較（同じ日数だけ遡った期間と比較）
        </label>
      )}
    </div>
  );
}
