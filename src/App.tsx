import { useCallback, useEffect, useState } from "react";
import { ApiError, getDashboard, getHealth } from "./api";
import type { DashboardResponse, HealthResponse } from "./types";

type LoadState = "loading" | "success" | "error";

function App() {
  const [state, setState] = useState<LoadState>("loading");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const checkConnectivity = useCallback(() => {
    setState("loading");
    setErrorMessage("");
    Promise.all([
      getHealth(),
      getDashboard({ scenario: "rules", period: "7d", channel: "all" }),
    ])
      .then(([healthResult, dashboardResult]) => {
        setHealth(healthResult);
        setDashboard(dashboardResult);
        setState("success");
      })
      .catch((error: unknown) => {
        const message =
          error instanceof ApiError
            ? error.message
            : "APIとの通信中に予期しないエラーが発生しました。";
        setErrorMessage(message);
        setState("error");
      });
  }, []);

  useEffect(() => {
    checkConnectivity();
  }, [checkConnectivity]);

  return (
    <div className="status-check">
      <h1>Fraud Decision Center</h1>
      <p className="subtitle">不正リスクを見抜き、正常な顧客体験と事業成長を守る</p>

      <div className="card">
        <p>
          {state === "loading" && <span className="badge badge-loading">確認中</span>}
          {state === "success" && <span className="badge badge-ok">API疎通OK</span>}
          {state === "error" && <span className="badge badge-error">エラー</span>}
        </p>

        {state === "loading" && <p>APIとの疎通を確認しています…</p>}

        {state === "error" && (
          <>
            <p>{errorMessage}</p>
            <button type="button" onClick={checkConnectivity}>
              再試行
            </button>
          </>
        )}

        {state === "success" && health && dashboard && (
          <>
            <p>
              バックエンド: {health.service}({health.status})
            </p>
            <p>
              概況ダッシュボードAPI: 総取引件数{" "}
              {dashboard.kpis.find((k) => k.key === "total_transactions")?.value.toLocaleString("ja-JP")}
              件を取得しました。
            </p>
            <p>データ更新時刻: {dashboard.data_updated_at}</p>
          </>
        )}
      </div>

      <p className="footer-note">
        本画面はPhase 1の疎通確認用の最小表示です。経営ダッシュボードと調査ワークベンチの本実装はPhase
        2・Phase 3で行います。本アプリはデモ用の合成データを使用しています。実際の取引判定や顧客データは含まれません。
      </p>
    </div>
  );
}

export default App;
