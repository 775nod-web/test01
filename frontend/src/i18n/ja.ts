/**
 * Centralized Japanese UI strings. Japanese is the default (and only) UI
 * language for this demo — there is no language toggle. Backend API
 * responses stay in English (risk_segment, value_segment, primary_driver,
 * recommended_action, recommended_channel, contact reason/channel are all
 * English enum-like values); this module translates them for display only.
 *
 * Do not scatter Japanese strings directly inside components — import from
 * here so every page stays consistent and translations can be found/fixed
 * in one place.
 */

export const NAV = {
  brand: "Retention Demo",
  executiveOverview: "経営サマリー",
  segmentExplorer: "顧客セグメント分析",
  retentionActions: "リテンション施策対象",
  poc: "PoCと今後の展開",
};

export const PAGE_TITLES = {
  executiveOverview: "経営サマリー",
  segmentExplorer: "顧客セグメント分析",
  customer360: "顧客360",
  retentionActions: "リテンション施策対象",
  poc: "PoCと今後の展開",
};

export const BUSINESS_QUESTIONS = {
  executiveOverview: "限られたリテンション予算をどこに集中すべきか？",
  segmentExplorer: "どの顧客行動パターンにキャンペーンで対応すべきか？",
  customer360: "なぜこの顧客を優先すべきか、どう対応すべきか？",
  retentionActions: "誰に、どのアクションを最初に届けるべきか？",
  poc: "本番導入の判断前に何を検証すべきか？",
};

export const COMMON = {
  syntheticBanner:
    'シミュレーションデータ — 実際の顧客・銀行データは含まれません。「シミュレーション値」と表示された数値は説明用の推定値であり、実際の財務数値ではありません。',
  simulated: "シミュレーション値",
  loading: "読み込み中…",
  error: "エラーが発生しました",
  downloadCsv: "CSVをダウンロード",
  clearFilters: "クリア",
  yes: "はい",
  no: "いいえ",
  none: "なし",
  all: "すべて",
  any: "指定なし",
};

export const RISK_SEGMENT_LABEL: Record<string, string> = {
  High: "高リスク",
  Medium: "中リスク",
  Low: "低リスク",
};

export const VALUE_SEGMENT_LABEL: Record<string, string> = {
  High: "高価値",
  Medium: "中価値",
  Low: "低価値",
};

export const HUMAN_REVIEW_REQUIRED_LABEL = "担当者による確認が必要";

export const AUDIENCE_LABEL = {
  broadCampaignAudience: "一律配信対象",
  prioritizedAudience: "優先施策対象",
};

export const FIELD_LABELS = {
  primaryDriver: "主なリスク要因",
  secondaryDriver: "副次的なリスク要因",
  recommendedAction: "推奨アクション",
  recommendedChannel: "推奨チャネル",
  estimatedValueAtRisk: "推定価値リスク",
  riskScore: "リスクスコア",
  riskSegment: "リスク区分",
  signalsDetected: "検知シグナル",
  totalCustomers: "総顧客数",
  highRiskCustomers: "高リスク顧客数",
  highRiskHighValue: "高リスク・高価値",
  tenure: "契約期間",
  currentBalance: "現在の残高",
  simulatedAnnualValue: "シミュレーション年間価値",
  priority: "優先順位",
  priorityTier: "優先度ティア",
  customer: "顧客",
  risk: "リスク",
  value: "価値",
  channel: "チャネル",
  review: "確認",
  mainDriver: "主な要因",
};

// English enum-like values from the backend -> Japanese display labels.
// Falls back to the raw value if a new value appears that isn't listed
// here yet, so the UI never silently shows "undefined".
export const DRIVER_LABEL_JA: Record<string, string> = {
  "Balance decline (90d)": "残高減少（90日）",
  "Salary deposit stopped": "給与振込停止",
  "Card spend decline (90d)": "カード利用減少（90日）",
  "App engagement decline (90d)": "アプリ利用減少（90日）",
  "Rising complaints": "苦情増加",
  "Long app inactivity": "長期アプリ未利用",
  "Unresolved service contact": "未解決の問い合わせ",
  "Product holding decreased": "保有商品数の減少",
  "No material risk driver": "重大なリスク要因なし",
  None: "なし",
};

export const ACTION_LABEL_JA: Record<string, string> = {
  "Priority service recovery": "優先サービスリカバリー",
  "Fee/service-plan review": "手数料・プラン見直し",
  "Targeted card benefit message": "カード特典の案内",
  "Personalized in-app engagement message": "アプリ内パーソナライズ通知",
  "Relationship review (balance outflow)": "取引関係レビュー（残高流出）",
  "Relationship review (income change)": "取引関係レビュー（収入変化）",
  "Product/portfolio review": "商品ポートフォリオ見直し",
  "No immediate action": "対応不要",
};

export const CHANNEL_LABEL_JA: Record<string, string> = {
  "Call Center": "コールセンター",
  "Push/App": "プッシュ通知／アプリ",
  Email: "メール",
  Branch: "店舗",
  Chat: "チャット",
  None: "なし",
};

export const CONTACT_REASON_LABEL_JA: Record<string, string> = {
  "Fee Question": "手数料に関する質問",
  Complaint: "苦情",
  "Service Request": "サービス依頼",
  "Product Inquiry": "商品に関する問い合わせ",
  "Technical Issue": "技術的な問題",
};

export const PRIORITY_EXPLANATION =
  "優先順位は、解約リスク、顧客価値、推定価値リスク、介入可能性を組み合わせて算出しています。";

function lookup(dict: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "—";
  return dict[value] ?? value;
}

export const t = {
  riskSegment: (v: string | null | undefined) => lookup(RISK_SEGMENT_LABEL, v),
  valueSegment: (v: string | null | undefined) => lookup(VALUE_SEGMENT_LABEL, v),
  driver: (v: string | null | undefined) => lookup(DRIVER_LABEL_JA, v),
  action: (v: string | null | undefined) => lookup(ACTION_LABEL_JA, v),
  channel: (v: string | null | undefined) => lookup(CHANNEL_LABEL_JA, v),
  contactReason: (v: string | null | undefined) => lookup(CONTACT_REASON_LABEL_JA, v),
  contactChannel: (v: string | null | undefined) => lookup(CHANNEL_LABEL_JA, v),
};
