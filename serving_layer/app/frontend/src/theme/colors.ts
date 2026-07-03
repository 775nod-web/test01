/**
 * カラートークン定義。
 *
 * - UI チャンパー（サイドバー・カード背景・バッジ）には Google スライド風の
 *   淡く鮮やかなパステルカラーを使う。
 * - グラフの系列色 (chartSeries) はアクセシビリティ検証済みの配色
 *   (dataviz skill の references/palette.md 準拠) を使う。パステルは
 *   コントラストが低くデータエンコードには不向きなため、装飾用途に限定する。
 * - ステータス色 (status) は churn_risk_flag 等の状態表示専用で、系列色や
 *   パステルとは独立して固定する。
 */

export const uiPastel = {
  blue: "#6FA8DC",
  green: "#93C47D",
  yellow: "#FFD966",
  red: "#E06666",
  purple: "#8E7CC3",
  teal: "#76A5AF",
  orange: "#F6B26B",
  pink: "#C27BA0",
} as const;

export const surface = {
  page: "#f9f9f7",
  card: "#fcfcfb",
  sidebar: "#eef3fb",
  border: "rgba(11,11,11,0.10)",
} as const;

export const ink = {
  primary: "#0b0b0b",
  secondary: "#52514e",
  muted: "#898781",
} as const;

/** アクセシビリティ検証済みのグラフ系列色。固定順で使用し、シャッフルしない。 */
export const chartSeries = [
  "#2a78d6", // blue
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
  "#e87ba4", // magenta
  "#eb6834", // orange
] as const;

export const status = {
  good: "#0ca30c",
  warning: "#fab219",
  serious: "#ec835a",
  critical: "#d03b3b",
} as const;

export const gridline = "#e1e0d9";
export const baseline = "#c3c2b7";
