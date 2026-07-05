import type { AlertRow } from "../types";

export function AlertBanner({ alerts }: { alerts: AlertRow[] }) {
  if (alerts.length === 0) {
    return null;
  }
  return (
    <div className="alert-banner">
      {alerts.slice(0, 3).map((alert) => (
        <div key={`${alert.store_id}-${alert.alert_date}`}>⚠ {alert.message}</div>
      ))}
      {alerts.length > 3 && <div>他 {alerts.length - 3} 件のアラートがあります</div>}
    </div>
  );
}
