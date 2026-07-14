import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { BarChart, type BarDatum } from "../components/BarChart";
import { PageHeader } from "../components/Layout";
import { KpiTile } from "../components/KpiTile";
import { ErrorState, LoadingState } from "../components/States";
import { ValueRiskMatrix } from "../components/ValueRiskMatrix";
import { BUSINESS_QUESTIONS, PAGE_TITLES, t } from "../i18n/ja";
import type { KpiResponse, RiskDistributionItem, TopDriverItem, ValueRiskMatrixItem } from "../types";

const RISK_COLOR: Record<string, string> = { High: "#EA4335", Medium: "#FBBC04", Low: "#34A853" };

export function ExecutiveOverview() {
  const [kpis, setKpis] = useState<KpiResponse | null>(null);
  const [riskDist, setRiskDist] = useState<RiskDistributionItem[] | null>(null);
  const [matrix, setMatrix] = useState<ValueRiskMatrixItem[] | null>(null);
  const [drivers, setDrivers] = useState<TopDriverItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.kpis(), api.riskDistribution(), api.valueRiskMatrix(), api.topRiskDrivers()])
      .then(([k, r, m, d]) => {
        setKpis(k);
        setRiskDist(r);
        setMatrix(m);
        setDrivers(d);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "データを読み込めませんでした。"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!kpis || !riskDist || !matrix || !drivers) return <LoadingState label="経営サマリーを読み込み中…" />;

  const prioritizedPctRaw = kpis.broad_campaign_audience_count
    ? (100 * kpis.prioritized_audience_count) / kpis.broad_campaign_audience_count
    : 0;
  const prioritizedPctLabel =
    prioritizedPctRaw > 0 && prioritizedPctRaw < 1 ? "1%未満" : `${Math.round(prioritizedPctRaw)}%`;

  const driverBars: BarDatum[] = drivers.map((d) => ({
    label: t.driver(d.primary_driver),
    value: d.customer_count,
    color: "#4285F4",
  }));

  return (
    <div>
      <PageHeader title={PAGE_TITLES.executiveOverview} question={BUSINESS_QUESTIONS.executiveOverview} />

      <p style={{ marginTop: -8, marginBottom: 20 }}>
        <Link to="/customers/CUST000001">デモ用固定顧客 CUST000001 の Customer 360 を見る →</Link>
      </p>

      <div className="grid grid--kpis">
        <KpiTile label="総顧客数" value={kpis.total_customers.toLocaleString()} />
        <KpiTile label="高リスク顧客数" value={kpis.high_risk_customers.toLocaleString()} variant="risk" />
        <KpiTile
          label="高リスク・高価値"
          value={kpis.high_risk_high_value_customers.toLocaleString()}
          variant="risk"
          tooltip="高リスクかつ高価値の顧客 — リテンション対応の最優先対象。"
        />
        <KpiTile
          label="推定価値リスク"
          value={`$${Math.round(kpis.estimated_value_at_risk_total_simulated).toLocaleString()}`}
          variant="value"
          footnote="シミュレーション値 — 実際の財務数値ではありません。"
        />
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <p className="section-title">一律配信対象 と 優先施策対象</p>
        <p className="section-subtitle">
          現在の一律配信は全顧客に対して行われています。優先施策対象に絞ると、対象は全体の
          {prioritizedPctLabel}になります: 高リスクかつ高／中価値、または中リスクかつ高価値の顧客で、
          それぞれに推奨アクションが設定され、連絡前に必ず担当者による確認が必要です。
        </p>
        <div className="grid grid--kpis">
          <KpiTile label="一律配信対象" value={kpis.broad_campaign_audience_count.toLocaleString()} />
          <KpiTile
            label="優先施策対象"
            value={kpis.prioritized_audience_count.toLocaleString()}
            variant="value"
            tooltip="（高リスク かつ 高／中価値）または（中リスク かつ 高価値）で、アクションが設定され担当者確認が必要な顧客。リテンション施策対象・CSV出力・主なリスク要因チャートと同じ定義です。"
          />
        </div>
      </div>

      <div className="grid grid--2col" style={{ marginTop: 20 }}>
        <div className="card">
          <p className="section-title">リスク分布</p>
          <p className="section-subtitle">各リスク区分に属する顧客数。</p>
          <BarChart
            data={riskDist.map((r) => ({
              label: `${t.riskSegment(r.risk_segment)}（平均スコア ${r.avg_risk_score}）`,
              value: r.customer_count,
              color: RISK_COLOR[r.risk_segment],
            }))}
          />
        </div>

        <div className="card">
          <p className="section-title">顧客価値 × 解約リスク</p>
          <p className="section-subtitle">リスクと価値は独立しています — 高価値の顧客が自動的に低リスクとは限りません。</p>
          <ValueRiskMatrix data={matrix} />
        </div>
      </div>

      <div className="card">
        <p className="section-title">優先対象顧客に多い主なリスク要因</p>
        <p className="section-subtitle">各リスクシグナルに該当する優先対象顧客数</p>
        <BarChart data={driverBars} />
      </div>
    </div>
  );
}
