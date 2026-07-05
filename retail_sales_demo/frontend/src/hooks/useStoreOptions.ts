import { useEffect, useState } from 'react';
import { fetchStoreRanking } from '../api/client';

export interface StoreOption {
  storeId: string;
  storeName: string;
}

/**
 * Phase 1 doesn't expose a dedicated "list of stores" endpoint, so store
 * options for filter UIs are derived from /api/store-ranking (unfiltered)
 * and de-duplicated by store_id. Fine for this demo's scale (5 stores);
 * revisit with a dedicated endpoint if the store count grows.
 */
export function useStoreOptions() {
  const [options, setOptions] = useState<StoreOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStoreRanking({})
      .then((rows) => {
        if (cancelled) return;
        const seen = new Map<string, StoreOption>();
        for (const row of rows) {
          if (!seen.has(row.store_id)) {
            seen.set(row.store_id, { storeId: row.store_id, storeName: row.store_name });
          }
        }
        setOptions([...seen.values()].sort((a, b) => a.storeId.localeCompare(b.storeId)));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { options, loading, error };
}
