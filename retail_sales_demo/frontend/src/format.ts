export function formatCurrency(value: number): string {
  return `¥${Math.round(value).toLocaleString('ja-JP')}`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString('ja-JP');
}

/** % change of `current` vs `previous`; null when there's no previous value to compare against. */
export function pctDelta(current: number, previous: number | null | undefined): number | null {
  if (previous == null || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

/** Same-length period immediately preceding [dateFrom, dateTo], for "compare to previous period". */
export function previousPeriod(dateFrom: string, dateTo: string): { from: string; to: string } {
  const from = new Date(dateFrom);
  const to = new Date(dateTo);
  const spanMs = to.getTime() - from.getTime();
  const prevTo = new Date(from.getTime() - 24 * 60 * 60 * 1000);
  const prevFrom = new Date(prevTo.getTime() - spanMs);
  return { from: prevFrom.toISOString().slice(0, 10), to: prevTo.toISOString().slice(0, 10) };
}
