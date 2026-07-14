import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { RiskBadge, ValueBadge } from "../components/Badges";
import { PageHeader } from "../components/Layout";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { BUSINESS_QUESTIONS, PAGE_TITLES, t } from "../i18n/ja";
import type { CustomerListItem, SegmentFilterOptions } from "../types";

function pct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(0)}%`;
}

interface Preset {
  key: string;
  label: string;
  riskSegment: string;
  valueSegment: string;
  balanceDecline: boolean;
  cardDecline: boolean;
  appDecline: boolean;
  complaintsOnly: boolean;
}

const PRESETS: Preset[] = [
  {
    key: "high_value_high_risk",
    label: "高価値・高リスク",
    riskSegment: "High",
    valueSegment: "High",
    balanceDecline: false,
    cardDecline: false,
    appDecline: false,
    complaintsOnly: false,
  },
  {
    key: "service_dissatisfaction",
    label: "サービス不満",
    riskSegment: "",
    valueSegment: "",
    balanceDecline: false,
    cardDecline: false,
    appDecline: false,
    complaintsOnly: true,
  },
  {
    key: "digital_disengagement",
    label: "デジタル離反兆候",
    riskSegment: "",
    valueSegment: "",
    balanceDecline: false,
    cardDecline: false,
    appDecline: true,
    complaintsOnly: false,
  },
  {
    key: "balance_outflow",
    label: "残高流出",
    riskSegment: "",
    valueSegment: "",
    balanceDecline: true,
    cardDecline: false,
    appDecline: false,
    complaintsOnly: false,
  },
  {
    key: "card_spend_decline",
    label: "カード利用低下",
    riskSegment: "",
    valueSegment: "",
    balanceDecline: false,
    cardDecline: true,
    appDecline: false,
    complaintsOnly: false,
  },
];

const DEFAULT_PRESET = PRESETS[0];

export function SegmentExplorer() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<SegmentFilterOptions | null>(null);
  const [riskSegment, setRiskSegment] = useState(DEFAULT_PRESET.riskSegment);
  const [valueSegment, setValueSegment] = useState(DEFAULT_PRESET.valueSegment);
  const [balanceDecline, setBalanceDecline] = useState(DEFAULT_PRESET.balanceDecline);
  const [cardDecline, setCardDecline] = useState(DEFAULT_PRESET.cardDecline);
  const [appDecline, setAppDecline] = useState(DEFAULT_PRESET.appDecline);
  const [complaintsOnly, setComplaintsOnly] = useState(DEFAULT_PRESET.complaintsOnly);
  const [maxProducts, setMaxProducts] = useState("");
  const [activePreset, setActivePreset] = useState<string | null>(DEFAULT_PRESET.key);

  function applyPreset(preset: Preset) {
    setRiskSegment(preset.riskSegment);
    setValueSegment(preset.valueSegment);
    setBalanceDecline(preset.balanceDecline);
    setCardDecline(preset.cardDecline);
    setAppDecline(preset.appDecline);
    setComplaintsOnly(preset.complaintsOnly);
    setMaxProducts("");
    setActivePreset(preset.key);
  }

  function clearFilters() {
    setRiskSegment("");
    setValueSegment("");
    setBalanceDecline(false);
    setCardDecline(false);
    setAppDecline(false);
    setComplaintsOnly(false);
    setMaxProducts("");
    setActivePreset(null);
  }

  const [items, setItems] = useState<CustomerListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.segmentFilterOptions().then(setOptions).catch(() => setOptions({ risk_segments: [], value_segments: [] }));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .customers({
        risk_segment: riskSegment || undefined,
        value_segment: valueSegment || undefined,
        max_product_count: maxProducts ? Number(maxProducts) : undefined,
        balance_decline_pct: balanceDecline ? -0.3 : undefined,
        card_spend_decline_pct: cardDecline ? -0.3 : undefined,
        app_decline_pct: appDecline ? -0.5 : undefined,
        min_complaints_90d: complaintsOnly ? 2 : undefined,
        limit: 200,
      })
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Unable to load customers."))
      .finally(() => setLoading(false));
  }, [riskSegment, valueSegment, balanceDecline, cardDecline, appDecline, complaintsOnly, maxProducts]);

  return (
    <div>
      <PageHeader title={PAGE_TITLES.segmentExplorer} question={BUSINESS_QUESTIONS.segmentExplorer} />

      <div className="card">
        <div className="filters-row" role="group" aria-label="プリセット">
          {PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              className={activePreset === preset.key ? "btn btn--primary" : "btn"}
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
          <button type="button" className="btn" onClick={clearFilters}>
            クリア
          </button>
        </div>
        <div className="filters-row">
          <div className="filter-field">
            <label htmlFor="risk-filter">リスク区分</label>
            <select
              id="risk-filter"
              value={riskSegment}
              onChange={(e) => {
                setRiskSegment(e.target.value);
                setActivePreset(null);
              }}
            >
              <option value="">すべて</option>
              {(options?.risk_segments ?? []).map((s) => (
                <option key={s} value={s}>
                  {t.riskSegment(s)}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="value-filter">価値区分</label>
            <select
              id="value-filter"
              value={valueSegment}
              onChange={(e) => {
                setValueSegment(e.target.value);
                setActivePreset(null);
              }}
            >
              <option value="">すべて</option>
              {(options?.value_segments ?? []).map((s) => (
                <option key={s} value={s}>
                  {t.valueSegment(s)}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-field">
            <label htmlFor="max-products">保有商品数</label>
            <select
              id="max-products"
              value={maxProducts}
              onChange={(e) => {
                setMaxProducts(e.target.value);
                setActivePreset(null);
              }}
            >
              <option value="">指定なし</option>
              <option value="1">1以下</option>
              <option value="2">2以下</option>
              <option value="3">3以下</option>
            </select>
          </div>
        </div>
        <div className="checkbox-row">
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={balanceDecline}
              onChange={(e) => {
                setBalanceDecline(e.target.checked);
                setActivePreset(null);
              }}
            />
            残高減少（90日で30%超）
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={cardDecline}
              onChange={(e) => {
                setCardDecline(e.target.checked);
                setActivePreset(null);
              }}
            />
            カード利用減少（90日で30%超）
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={appDecline}
              onChange={(e) => {
                setAppDecline(e.target.checked);
                setActivePreset(null);
              }}
            />
            アプリ利用減少（90日で50%超）
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={complaintsOnly}
              onChange={(e) => {
                setComplaintsOnly(e.target.checked);
                setActivePreset(null);
              }}
            />
            苦情2件以上（90日）
          </label>
        </div>

        {error && <ErrorState message={error} />}
        {!error && loading && <LoadingState label="顧客データを読み込み中…" />}
        {!error && !loading && items && items.length === 0 && <EmptyState />}
        {!error && !loading && items && items.length > 0 && (
          <>
            <p className="section-subtitle">{items.length} 件が該当（最大200件まで表示）。</p>
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">顧客</th>
                    <th scope="col">リスク</th>
                    <th scope="col">価値</th>
                    <th scope="col">主なリスク要因</th>
                    <th scope="col">残高Δ 90日</th>
                    <th scope="col">カードΔ 90日</th>
                    <th scope="col">アプリΔ 90日</th>
                    <th scope="col">苦情件数 90日</th>
                    <th scope="col">推奨アクション</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr
                      key={c.customer_id}
                      onClick={() => navigate(`/customers/${c.customer_id}`)}
                      tabIndex={0}
                      role="button"
                      aria-label={`${c.customer_id} の Customer 360 を開く`}
                      onKeyDown={(e) => e.key === "Enter" && navigate(`/customers/${c.customer_id}`)}
                    >
                      <td>{c.customer_id}</td>
                      <td>
                        <RiskBadge segment={c.risk_segment} />
                      </td>
                      <td>
                        <ValueBadge segment={c.value_segment} />
                      </td>
                      <td>{t.driver(c.primary_driver)}</td>
                      <td>{pct(c.balance_change_90d_pct)}</td>
                      <td>{pct(c.card_spend_change_90d_pct)}</td>
                      <td>{pct(c.login_change_90d_pct)}</td>
                      <td>{c.complaint_count_90d}</td>
                      <td>{t.action(c.recommended_action)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
