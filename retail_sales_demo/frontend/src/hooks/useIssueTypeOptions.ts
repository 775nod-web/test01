import { useEffect, useState } from 'react';
import { fetchQuarantineReport } from '../api/client';

/** Derives the list of distinct issue_type values from an unfiltered fetch, for a filter dropdown. */
export function useIssueTypeOptions() {
  const [options, setOptions] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchQuarantineReport({})
      .then((rows) => {
        if (cancelled) return;
        setOptions([...new Set(rows.map((r) => r.issue_type))].sort());
      })
      .catch(() => {
        /* filter dropdown just stays empty; the report table itself surfaces fetch errors */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return options;
}
