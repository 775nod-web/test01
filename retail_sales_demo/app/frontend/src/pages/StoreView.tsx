import { useEffect, useState } from "react";
import { fetchDailyStoreSales, fetchKpiSummary } from "../api/client";
import type { DailyStoreSales, KpiSummary } from "../types";
import { KpiCard } from "../components/KpiCard";

/**
 * 店長ビュー。
 * 実際の店舗絞り込みはサーバー側（Unity Catalog行フィルタ、またはAPI側の
 * user_store_mapping参照）でログインユーザーに基づき自動的に行われる。
 * このデモではデフォルトで /api/kpi-summary, /api/daily-store-sales を
 * 店舗指定なしで呼び出し、サーバー側フィルタの結果をそのまま表示する。
 */
export function StoreView() {
  const [kpi, setKpi] = useState<KpiSummary | null>(null);
  const [rows, setRows] = useState<DailyStoreSales[]>([]);

  useEffect(() => {
    fetchKpiSummary().then(setKpi).catch(console.error);
    fetchDailyStoreSales().then(setRows).catch(console.error);
  }, []);

  return (
    <div>
      <h2>店舗ビュー</h2>
      <p style={{ fontSize: 13, color: "#5f6368" }}>
        ※表示データはサーバー側のアクセス制御により、ログインユーザーが担当する店舗のみに自動的に絞り込まれます。
      </p>

      {kpi && (
        <div className="kpi-grid">
          <KpiCard label="Net Sales" value={kpi.net_sales.toLocaleString()} accentColor="var(--color-primary)" />
          <KpiCard label="Transaction Count" value={kpi.transaction_count.toLocaleString()} accentColor="var(--color-positive)" />
          <KpiCard
            label="Average Basket Size"
            value={kpi.average_basket_size.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            accentColor="var(--color-negative)"
          />
        </div>
      )}

      <div className="card">
        <h3>日別売上明細</h3>
        <table>
          <thead>
            <tr>
              <th>日付</th>
              <th>店舗名</th>
              <th>取引件数</th>
              <th>数量</th>
              <th>売上金額</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.store_id}-${row.sales_date}`}>
                <td>{row.sales_date}</td>
                <td>{row.store_name}</td>
                <td>{row.transaction_count.toLocaleString()}</td>
                <td>{row.total_quantity.toLocaleString()}</td>
                <td>{row.total_sales_amount.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
