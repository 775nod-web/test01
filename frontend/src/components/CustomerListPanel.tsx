import type { CustomerSummary } from "../types";
import { RiskBadge } from "./RiskBadge";

interface Props {
  customers: CustomerSummary[];
  selectedCustomerId: string | null;
  onSelect: (customerId: string) => void;
}

export function CustomerListPanel({ customers, selectedCustomerId, onSelect }: Props) {
  return (
    <ul className="customer-list">
      {customers.map((customer) => {
        const isSelected = customer.customer_id === selectedCustomerId;
        return (
          <li key={customer.customer_id}>
            <button
              type="button"
              className={isSelected ? "customer-list__item customer-list__item--selected" : "customer-list__item"}
              onClick={() => onSelect(customer.customer_id)}
              aria-pressed={isSelected}
            >
              <div className="customer-list__item-header">
                <span className="customer-list__name">{customer.display_name}</span>
                <RiskBadge band={customer.risk_band} label={customer.risk_band_label} />
              </div>
              <div className="customer-list__item-meta">
                休眠確率 {Math.round(customer.churn_probability * 100)}% ・ 利用サービス数{" "}
                {customer.service_count}
              </div>
              {customer.top_reason && (
                <div className="customer-list__item-reason">{customer.top_reason}</div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
