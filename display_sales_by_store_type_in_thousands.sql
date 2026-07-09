-- Databricks SQL ノートブック用
-- retail.sales_by_store_type_monthly の total_sales_amount を1000円単位で表示する
--
-- 前提：save_sales_by_store_type_truncated.py を実行済みで、
--       retail.sales_by_store_type_monthly が保存されていること

SELECT
  store_type,
  ROUND(total_sales_amount / 1000, 0) AS total_sales_amount_thousand_yen  -- 1000円単位（千円）に換算
FROM retail.sales_by_store_type_monthly
ORDER BY total_sales_amount_thousand_yen DESC;
