import type { KpiUnit } from "../types";

export function formatByUnit(value: number, unit: KpiUnit): string {
  switch (unit) {
    case "count":
      return `${Math.round(value).toLocaleString("ja-JP")}件`;
    case "jpy":
      return `¥${Math.round(value).toLocaleString("ja-JP")}`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "minutes":
      return `${value.toFixed(1)}分`;
    default:
      return `${value}`;
  }
}

export function formatDelta(delta: number, unit: KpiUnit): string {
  const sign = delta > 0 ? "+" : delta < 0 ? "-" : "±";
  const abs = Math.abs(delta);
  switch (unit) {
    case "count":
      return `${sign}${Math.round(abs).toLocaleString("ja-JP")}件`;
    case "jpy":
      return `${sign}¥${Math.round(abs).toLocaleString("ja-JP")}`;
    case "percent":
      return `${sign}${(abs * 100).toFixed(1)}pt`;
    case "minutes":
      return `${sign}${abs.toFixed(1)}分`;
    default:
      return `${sign}${abs}`;
  }
}

export function formatJpy(value: number): string {
  return `¥${Math.round(value).toLocaleString("ja-JP")}`;
}

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00+09:00`);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
