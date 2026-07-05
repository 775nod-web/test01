import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell } from "recharts";
import { fetchCategorySales, fetchStoreRanking } from "../api/client";
import type { CategorySales, StoreRanking } from "../types";

const PALETTE = ["#aecbfa", "#d7aefb", "#a8dab5", "#fde293", "#f6aea9"];

export function MerchandisingView() {
  const [categories, setCategories] = useState<CategorySales[]>([]);
  const [ranking, setRanking] = useState<StoreRanking[]>([]);

  useEffect(() => {
    fetchCategorySales().then(setCategories).catch(console.error);
    fetchStoreRanking(10).then(setRanking).catch(console.error);
  }, []);

  return (
    <div>
      <h2>商品企画ビュー</h2>

      <div className="card">
        <h3>カテゴリ別売上構成</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={categories}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="category" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="total_sales_amount">
              {categories.map((_, index) => (
                <Cell key={index} fill={PALETTE[index % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>店舗ランキング（Top 10）</h3>
        <table>
          <thead>
            <tr>
              <th>順位</th>
              <th>店舗名</th>
              <th>地域</th>
              <th>売上金額</th>
              <th>取引件数</th>
            </tr>
          </thead>
          <tbody>
            {ranking.map((row) => (
              <tr key={row.store_id}>
                <td>{row.sales_rank}</td>
                <td>{row.store_name}</td>
                <td>{row.region}</td>
                <td>{row.total_sales_amount.toLocaleString()}</td>
                <td>{row.transaction_count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
