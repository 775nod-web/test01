import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { HumanReviewBadge, RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { BUSINESS_QUESTIONS, COMMON, PAGE_TITLES, PRIORITY_EXPLANATION, t } from "../i18n/ja";
import type { RetentionActionItem } from "../types";

const PAGE_SIZE = 25;

export function RetentionActions() {
  const navigate = useNavigate();
  const [riskSegment, setRiskSegment] = useState("");
  const [valueSegment, setValueSegment] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<RetentionActionItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setOffset(0);
  }, [riskSegment, valueSegment]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .retentionActions({
        risk_segment: riskSegment || undefined,
        value_segment: valueSegment || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "リテンション施策対象を読み込めませんでした。"))
      .finally(() => setLoading(false));
  }, [riskSegment, valueSegment, offset]);

  const exportUrl = api.retentionActionsExportUrl({
    risk_segment: riskSegment || undefined,
    value_segment: valueSegment || undefined,
  });

  return (
    <div>
      <PageHeader title={PAGE_TITLES.retentionActions} question={BUSINESS_QUESTIONS.retentionActions} />
      <p className="section-subtitle" style={{ marginTop: -8, marginBottom: 20 }}>
        {PRIORITY_EXPLANATION}
      </p>

      <div className="card">
        <div className="filters-row">
          <div className="filter-field">
            <label htmlFor="ra-risk">リスク区分</label>
            <select id="ra-risk" value={riskSegment} onChange={(e) => setRiskSegment(e.target.value)}>
              <option value="">高＋中</option>
              <option value="High">高のみ</option>
              <option value="Medium">中のみ</option>
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="ra-value">価値区分</label>
            <select id="ra-value" value={valueSegment} onChange={(e) => setValueSegment(e.target.value)}>
              <option value="">すべて</option>
              <option value="High">高</option>
              <option value="Medium">中</option>
              <option value="Low">低</option>
            </select>
          </div>
          <a className="btn btn--primary" href={exportUrl} download style={{ textDecoration: "none" }}>
            {COMMON.downloadCsv}
          </a>
        </div>

        {error && <ErrorState message={error} />}
        {!error && loading && <LoadingState label="リテンション施策対象を読み込み中…" />}
        {!error && !loading && items && items.length === 0 && (
          <EmptyState message="この条件に一致する顧客はいません。" />
        )}
        {!error && !loading && items && items.length > 0 && (
          <>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">優先順位</th>
                    <th scope="col">ティア</th>
                    <th scope="col">顧客</th>
                    <th scope="col">リスク</th>
                    <th scope="col">価値</th>
                    <th scope="col">主な要因</th>
                    <th scope="col">推奨アクション</th>
                    <th scope="col">チャネル</th>
                    <th scope="col">推定価値リスク</th>
                    <th scope="col">確認</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr
                      key={r.customer_id}
                      onClick={() => navigate(`/customers/${r.customer_id}`)}
                      tabIndex={0}
                      role="button"
                      aria-label={`${r.customer_id} の Customer 360 を開く`}
                      onKeyDown={(e) => e.key === "Enter" && navigate(`/customers/${r.customer_id}`)}
                    >
                      <td>#{r.action_priority_rank}</td>
                      <td>{r.priority_tier}</td>
                      <td>{r.customer_id}</td>
                      <td>
                        <RiskBadge segment={r.risk_segment} />
                      </td>
                      <td>
                        <ValueBadge segment={r.value_segment} />
                      </td>
                      <td>{t.driver(r.primary_driver)}</td>
                      <td>{t.action(r.recommended_action)}</td>
                      <td>{t.channel(r.recommended_channel)}</td>
                      <td>${Math.round(r.estimated_value_at_risk).toLocaleString()}</td>
                      <td>
                        <HumanReviewBadge required={r.human_review_required} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination-row">
              <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                前へ
              </button>
              <span>
                {offset + 1}〜{offset + items.length} 件を表示
              </span>
              <button
                className="btn"
                disabled={items.length < PAGE_SIZE}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                次へ
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
