-- ======================================================
-- CloudNest ダッシュボード用 SQL クエリ集
-- ======================================================
-- Databricks SQL / AI/BI Dashboard にそのまま貼り付けて可視化できるクエリ集。
-- 想定ペルソナ別に3セクションに分けている：
--   A. 経営層向け（週次サマリー） … 課題5対応
--   B. Customer Success チーム向け（優先対応リスト） … 課題2対応
--   C. データサイエンスチーム向け（学習データ確認） … 課題6対応
--
-- 前提：01〜06 のノートブックを実行済みであること


-- ==================================================
-- A-1. 週次 ARR at risk トレンド（経営層向け・折れ線グラフ推奨）
-- ==================================================
SELECT
  as_of_date,
  ROUND(SUM(CASE WHEN risk_tier = 'AtRisk' THEN arr_usd ELSE 0 END), 0) AS at_risk_arr_usd,
  ROUND(SUM(CASE WHEN risk_tier = 'Watch'  THEN arr_usd ELSE 0 END), 0) AS watch_arr_usd,
  ROUND(SUM(arr_at_risk_usd), 0)                                       AS expected_arr_at_risk_usd,
  ROUND(SUM(arr_usd), 0)                                                AS total_arr_usd
FROM gold.cloudnest_gold_health_score_history
GROUP BY as_of_date
ORDER BY as_of_date;


-- ==================================================
-- A-2. 現在のリスクティア分布（経営層向け・ドーナツ/棒グラフ推奨）
-- ==================================================
SELECT
  risk_tier,
  COUNT(*)                       AS customer_count,
  ROUND(SUM(arr_usd), 0)         AS total_arr_usd,
  ROUND(SUM(arr_at_risk_usd), 0) AS arr_at_risk_usd,
  ROUND(AVG(health_score), 1)    AS avg_health_score
FROM gold.cloudnest_gold_health_score_latest
GROUP BY risk_tier
ORDER BY
  CASE risk_tier WHEN 'AtRisk' THEN 1 WHEN 'Watch' THEN 2 ELSE 3 END;


-- ==================================================
-- A-3. 業界別・地域別のリスク集中度（経営層向け・ヒートマップ推奨）
-- ==================================================
SELECT
  c.industry,
  c.region,
  COUNT(*)                                                   AS customer_count,
  ROUND(SUM(CASE WHEN h.risk_tier = 'AtRisk' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS at_risk_pct,
  ROUND(SUM(h.arr_at_risk_usd), 0)                            AS arr_at_risk_usd
FROM gold.cloudnest_gold_customer_360 c
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id)
GROUP BY c.industry, c.region
ORDER BY at_risk_pct DESC;


-- ==================================================
-- A-4. 契約更新カレンダー × リスク（今後90日以内に更新を迎える顧客のリスク内訳）
-- ==================================================
SELECT
  c.customer_id,
  c.company_name,
  c.csm_owner,
  c.days_to_renewal,
  c.arr_usd,
  h.risk_tier,
  h.health_score,
  h.top_risk_reason
FROM gold.cloudnest_gold_customer_360 c
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id)
WHERE c.days_to_renewal BETWEEN 0 AND 90
ORDER BY h.health_score ASC, c.arr_usd DESC;


-- ==================================================
-- B-1. CSM別 優先対応リスト（Customer Successチーム向け・トリアージビュー）
-- ==================================================
SELECT
  c.csm_owner,
  c.customer_id,
  c.company_name,
  h.risk_tier,
  h.health_score,
  c.arr_usd,
  c.days_to_renewal,
  h.top_risk_reason,
  c.usage_trend_pct,
  c.tickets_last_90d,
  c.avg_csat_last_90d,
  c.overdue_invoices_last_180d
FROM gold.cloudnest_gold_customer_360 c
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id)
WHERE h.risk_tier IN ('AtRisk', 'Watch')
ORDER BY c.csm_owner, h.health_score ASC, c.arr_usd DESC;


-- ==================================================
-- B-2. CSM別ワークロード（担当リスク件数の偏りを可視化 → リソース再配分の判断材料）
-- ==================================================
SELECT
  c.csm_owner,
  COUNT(*)                                                              AS total_accounts,
  SUM(CASE WHEN h.risk_tier = 'AtRisk' THEN 1 ELSE 0 END)               AS at_risk_accounts,
  SUM(CASE WHEN h.risk_tier = 'AtRisk' THEN c.arr_usd ELSE 0 END)       AS at_risk_arr_usd
FROM gold.cloudnest_gold_customer_360 c
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id)
GROUP BY c.csm_owner
ORDER BY at_risk_arr_usd DESC;


-- ==================================================
-- B-3. サポートチケットの内容と解約リスクの相関（テキスト分析結果を活用）
-- ==================================================
SELECT
  h.risk_tier,
  t.predicted_topic,
  t.predicted_sentiment,
  COUNT(*) AS ticket_count
FROM gold.cloudnest_gold_support_tickets_nlp t
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id)
WHERE t.created_date >= date_sub(current_date(), 90)
GROUP BY h.risk_tier, t.predicted_topic, t.predicted_sentiment
ORDER BY h.risk_tier, ticket_count DESC;


-- ==================================================
-- C-1. データサイエンスチーム向け：解約予測モデルの学習データセット概要
--       （customer_360 + health_score + 実際の解約結果（is_churned）を結合）
-- ==================================================
SELECT
  c.customer_id,
  c.industry,
  c.employee_band,
  c.region,
  c.plan,
  c.arr_usd,
  c.licensed_seats,
  c.usage_trend_pct,
  c.seat_utilization_rate,
  c.tickets_last_90d,
  c.avg_csat_last_90d,
  c.overdue_invoices_last_180d,
  h.health_score,
  h.risk_tier,
  c.is_churned                                     -- 教師ラベル（解約有無）
FROM gold.cloudnest_gold_customer_360 c
JOIN gold.cloudnest_gold_health_score_latest h USING (customer_id);
