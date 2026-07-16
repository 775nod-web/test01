import type { CustomerDetail } from "../types";
import { UsageTrendChart } from "./UsageTrendChart";

const PERIOD_LABELS = ["3か月前", "2か月前", "1か月前", "直近"];

function formatYen(amount: number): string {
  return `${amount.toLocaleString("ja-JP")}円`;
}

function formatDays(days: number | null): string {
  if (days === null) {
    return "利用履歴なし";
  }
  if (days === 0) {
    return "本日利用";
  }
  return `${days}日前`;
}

export function Customer360Panel({ customer }: { customer: CustomerDetail }) {
  const ec = customer.services.ec;
  const qrCard = customer.combined_qr_card;

  return (
    <div className="customer360">
      <div className="customer360__header">
        <h3 className="customer360__name">{customer.display_name}</h3>
        <span className="customer360__service-count">
          利用サービス数 {customer.service_count}
          {customer.previous_service_count !== customer.service_count && (
            <span className="customer360__service-count-prev">
              （前期 {customer.previous_service_count}）
            </span>
          )}
        </span>
      </div>

      {ec && qrCard && (
        <UsageTrendChart
          periodLabels={PERIOD_LABELS}
          series={[
            { label: "EC", color: "var(--color-blue-600)", values: ec.monthly_amount },
            { label: "QR・カード", color: "var(--color-magenta-600)", values: qrCard.monthly_amount },
          ]}
        />
      )}

      <div className="customer360__grid">
        {ec && (
          <div className="customer360__metric">
            <span className="customer360__metric-label">EC最終利用</span>
            <span className="customer360__metric-value">{formatDays(ec.days_since_last_used)}</span>
            <span className="customer360__metric-sub">
              直近 {formatYen(ec.monthly_amount[ec.monthly_amount.length - 1])}
            </span>
          </div>
        )}
        {qrCard && (
          <div className="customer360__metric">
            <span className="customer360__metric-label">QR・カード最終利用</span>
            <span className="customer360__metric-value">{formatDays(qrCard.days_since_last_used)}</span>
            <span className="customer360__metric-sub">
              直近 {formatYen(qrCard.monthly_amount[qrCard.monthly_amount.length - 1])}
            </span>
          </div>
        )}
        <div className="customer360__metric">
          <span className="customer360__metric-label">問い合わせ</span>
          <span className="customer360__metric-value">
            {customer.support_summary.inquiry_count}件
          </span>
          <span className="customer360__metric-sub">
            {customer.support_summary.recent_categories[0] ?? "履歴なし"}
          </span>
        </div>
      </div>

      <p className="customer360__sources">データソース: {customer.data_sources.join(" / ")}</p>
    </div>
  );
}
