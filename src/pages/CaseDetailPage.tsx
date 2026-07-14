import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getCaseDetail } from "../api";
import Badge, { actionTone, priorityTone, statusTone } from "../components/common/Badge";
import type { CaseDetail } from "../types";
import { formatJpy } from "../utils/format";

type LoadState = "loading" | "success" | "error" | "not_found";

function CaseDetailPage() {
  const { transactionId = "" } = useParams<{ transactionId: string }>();
  const [state, setState] = useState<LoadState>("loading");
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const load = useCallback(() => {
    setState("loading");
    getCaseDetail(transactionId)
      .then((result) => {
        setDetail(result);
        setState("success");
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
          setState("not_found");
          return;
        }
        setErrorMessage(error instanceof ApiError ? error.message : "ケース詳細の取得に失敗しました。");
        setState("error");
      });
  }, [transactionId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="case-detail-page">
      <p>
        <Link to="/">← 概況ダッシュボードへ戻る</Link>
      </p>

      {state === "loading" && (
        <div className="card" role="status">
          <span className="badge badge-loading">読み込み中</span>
          <p>ケース詳細を取得しています…</p>
        </div>
      )}

      {state === "not_found" && (
        <div className="card" role="alert">
          <span className="badge badge-tone-red">見つかりません</span>
          <p>取引ID「{transactionId}」のケースは見つかりませんでした。</p>
        </div>
      )}

      {state === "error" && (
        <div className="card" role="alert">
          <span className="badge badge-tone-red">エラー</span>
          <p>{errorMessage}</p>
          <button type="button" onClick={load}>
            再試行
          </button>
        </div>
      )}

      {state === "success" && detail && (
        <>
          <section className="card summary-banner">
            <div className="summary-banner-top">
              <h1 className="mono">{detail.transaction_id}</h1>
              <div className="summary-banner-badges">
                <Badge tone={priorityTone(detail.priority)}>優先度: {detail.priority}</Badge>
                <Badge tone={statusTone(detail.status)}>{detail.status}</Badge>
                <Badge tone={actionTone(detail.recommended_action)}>推奨: {detail.recommended_action}</Badge>
              </div>
            </div>
            <dl className="summary-grid">
              <div>
                <dt>リスクスコア</dt>
                <dd>{detail.risk_score.toFixed(2)}</dd>
              </div>
              <div>
                <dt>取引金額</dt>
                <dd>{formatJpy(detail.amount)}</dd>
              </div>
              <div>
                <dt>取引日時</dt>
                <dd>{detail.transaction_datetime}</dd>
              </div>
              <div>
                <dt>加盟店</dt>
                <dd>{detail.merchant}</dd>
              </div>
              <div>
                <dt>顧客ID</dt>
                <dd>{detail.customer_id}</dd>
              </div>
              <div>
                <dt>チャネル</dt>
                <dd>{detail.channel}</dd>
              </div>
            </dl>
            <p className="disclaimer-text">{detail.disclaimer}</p>
          </section>

          <section className="card" aria-labelledby="risk-factor-heading">
            <h2 id="risk-factor-heading">なぜ確認が必要か（主要リスク要因）</h2>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">要因</th>
                    <th scope="col">観測値</th>
                    <th scope="col">通常値</th>
                    <th scope="col">寄与度</th>
                    <th scope="col">説明</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.risk_factors.map((factor) => (
                    <tr key={factor.name}>
                      <td>{factor.name}</td>
                      <td>{factor.observed_value}</td>
                      <td>{factor.normal_value}</td>
                      <td>
                        <Badge
                          tone={factor.contribution === "高" ? "red" : factor.contribution === "中" ? "orange" : "gray"}
                        >
                          {factor.contribution}
                        </Badge>
                      </td>
                      <td>{factor.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card" aria-labelledby="rule-ai-heading">
            <h2 id="rule-ai-heading">判定根拠</h2>
            <h3 className="chart-subheading">既存ルール該当理由</h3>
            <ul>
              {detail.rule_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <h3 className="chart-subheading">AIスコア上位要因</h3>
            <ul>
              {detail.ai_top_factors.map((f) => (
                <li key={f.name}>
                  {f.name}（寄与度 {(f.weight * 100).toFixed(0)}%）— {f.description}
                </li>
              ))}
            </ul>
            <p className="meta-line">
              使用モデルバージョン: {detail.model_version} ／ 判定日時: {detail.decision_datetime} ／ データ更新時刻:{" "}
              {detail.data_updated_at}
            </p>
          </section>

          <div className="card phase-note">
            調査結果の登録、顧客の通常行動比較、取引タイムライン、関連情報、監査ログなどの詳細な調査ワークベンチ機能は
            Phase 3で実装予定です。
          </div>
        </>
      )}
    </div>
  );
}

export default CaseDetailPage;
