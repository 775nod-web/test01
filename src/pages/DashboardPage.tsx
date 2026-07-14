import { useCallback, useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { ApiError, getDashboard } from "../api";
import type { LayoutContext } from "../components/layout/Layout";
import ComparisonCard from "../components/dashboard/ComparisonCard";
import FilterBar from "../components/dashboard/FilterBar";
import HighRiskTable from "../components/dashboard/HighRiskTable";
import InvestigationQueueCard from "../components/dashboard/InvestigationQueueCard";
import KpiCard from "../components/dashboard/KpiCard";
import LossChart from "../components/dashboard/LossChart";
import RateChart from "../components/dashboard/RateChart";
import RiskDistributionChart from "../components/dashboard/RiskDistributionChart";
import type { Channel, DashboardResponse, Period, Scenario } from "../types";

type LoadState = "loading" | "success" | "error";

function DashboardPage() {
  const { setDataUpdatedAt } = useOutletContext<LayoutContext>();
  const [period, setPeriod] = useState<Period>("7d");
  const [scenario, setScenario] = useState<Scenario>("rules");
  const [channel, setChannel] = useState<Channel>("all");
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const load = useCallback(
    (nextPeriod: Period, nextScenario: Scenario, nextChannel: Channel) => {
      setState("loading");
      setErrorMessage("");
      getDashboard({ period: nextPeriod, scenario: nextScenario, channel: nextChannel })
        .then((result) => {
          setData(result);
          setState("success");
          setDataUpdatedAt(result.data_updated_at);
        })
        .catch((error: unknown) => {
          const message = error instanceof ApiError ? error.message : "ダッシュボードの取得に失敗しました。";
          setErrorMessage(message);
          setState("error");
        });
    },
    [setDataUpdatedAt],
  );

  useEffect(() => {
    load(period, scenario, channel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilterChange(next: { period: Period; scenario: Scenario; channel: Channel }) {
    setPeriod(next.period);
    setScenario(next.scenario);
    setChannel(next.channel);
    load(next.period, next.scenario, next.channel);
  }

  const primaryKpis = data?.kpis.filter((k) => k.is_primary) ?? [];
  const secondaryKpis = data?.kpis.filter((k) => !k.is_primary) ?? [];

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>不正対策 経営ダッシュボード</h1>
        <p className="page-description">不正損失、正常承認率、顧客影響、調査負荷を一つの画面で確認します。</p>
      </div>

      <FilterBar period={period} scenario={scenario} channel={channel} onChange={handleFilterChange} />

      {state === "loading" && (
        <div className="card" role="status">
          <span className="badge badge-loading">読み込み中</span>
          <p>ダッシュボードデータを取得しています…</p>
        </div>
      )}

      {state === "error" && (
        <div className="card" role="alert">
          <span className="badge badge-tone-red">エラー</span>
          <p>{errorMessage}</p>
          <button type="button" onClick={() => load(period, scenario, channel)}>
            再試行
          </button>
        </div>
      )}

      {state === "success" && data && (
        <>
          <div className="kpi-grid kpi-grid-primary">
            {primaryKpis.map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} size="large" />
            ))}
          </div>

          <div className="kpi-grid kpi-grid-secondary">
            {secondaryKpis.map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} size="small" />
            ))}
          </div>

          <ComparisonCard comparison={data.comparison} activeScenario={scenario} />

          <div className="chart-grid">
            <RateChart data={data.rate_series} />
            <LossChart data={data.loss_series} />
            <RiskDistributionChart data={data.risk_distribution} />
            <InvestigationQueueCard queue={data.investigation_queue} />
          </div>

          <HighRiskTable rows={data.high_risk_transactions} />
        </>
      )}
    </div>
  );
}

export default DashboardPage;
