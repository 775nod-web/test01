import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { Collapsible } from "../components/Collapsible";
import { PageHeader } from "../components/Layout";
import { ErrorState, LoadingState } from "../components/States";
import { BUSINESS_QUESTIONS, PAGE_TITLES } from "../i18n/ja";
import type { PocSummaryResponse } from "../types";

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="card">
      <p className="section-title">{title}</p>
      <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.6 }}>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function PocFutureExpansion() {
  const [data, setData] = useState<PocSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .pocSummary()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "このページを読み込めませんでした。"));
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!data) return <LoadingState label="読み込み中…" />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.poc} question={BUSINESS_QUESTIONS.poc} />

      {/* CLAUDE.md 要件は変わらず満たしつつ、Cスイート向け10分デモとして
          冒頭を3ブロック（確認すること／成功基準／次のアクション）に簡潔化。
          詳細情報は下部の折りたたみに移動（削除はしていない）。 */}
      <div className="grid grid--2col">
        <ListCard title="PoCで確認すること" items={data.must_validate_with_bank_data} />
        <ListCard title="成功基準" items={data.poc_success_metrics} />
      </div>

      <div className="card">
        <p className="section-title">次のアクション</p>
        <p className="section-subtitle" style={{ fontSize: 15 }}>
          PoC設計ワークショップでビジネス目的、成功基準、対象データ、実施環境を合意する
        </p>
      </div>

      <div className="card">
        <p className="section-title">Customer 360の将来拡張（クロスセル）</p>
        <p className="section-subtitle">{data.cross_sell_reuse_note}</p>
        {data.cross_sell_sample.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">顧客</th>
                  <th scope="col">価値</th>
                  <th scope="col">保有商品数</th>
                  <th scope="col">アプリエンゲージメントスコア</th>
                </tr>
              </thead>
              <tbody>
                {data.cross_sell_sample.map((c) => (
                  <tr key={c.customer_id} style={{ cursor: "default" }}>
                    <td>{c.customer_id}</td>
                    <td>{c.value_segment}</td>
                    <td>{c.product_count}</td>
                    <td>{c.app_engagement_score?.toFixed(0) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Collapsible title="詳細情報：シミュレーション内容・Free Edition制約・スコア計算">
        <p className="section-subtitle" style={{ marginTop: 0 }}>
          本デモで何がシミュレーションか
        </p>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.6, marginBottom: 16 }}>
          {data.synthetic_elements.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
        <p className="section-subtitle">Free Editionで実装していない機能</p>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, lineHeight: 1.6, marginBottom: 16 }}>
          {data.free_edition_limitations.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
        <p className="section-subtitle">リスクスコアの計算方法</p>
        <p style={{ fontSize: 14, lineHeight: 1.6 }}>
          8つのシグナルの加点方式による透明なポイントスコア（最大129点、100点満点表示にも正規化）。
          予測モデルではなく設定可能なビジネスルールです。詳細は docs/risk-scoring.md を参照してください。
        </p>
      </Collapsible>

      {data.ml_comparison.length > 0 && (
        <Collapsible title="技術補足：任意の機械学習比較" badge="任意">
          <p className="section-subtitle" style={{ marginTop: 0 }}>
            アプリ本体はルールベースのスコアで動作します。この比較は完全に任意の技術検証であり、
            評価はシミュレーションデータ上のものです。実データでの性能を保証するものではなく、
            PoCでは実データによる再評価が必要です。
          </p>
          <p className="section-subtitle">{data.ml_comparison_note}</p>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">手法</th>
                  <th scope="col">適合率</th>
                  <th scope="col">再現率</th>
                  <th scope="col">ROC-AUC</th>
                  <th scope="col">補足</th>
                </tr>
              </thead>
              <tbody>
                {data.ml_comparison.map((row) => (
                  <tr key={row.approach} style={{ cursor: "default" }}>
                    <td>{row.approach}</td>
                    <td>{row.precision.toFixed(3)}</td>
                    <td>{row.recall.toFixed(3)}</td>
                    <td>{row.roc_auc.toFixed(3)}</td>
                    <td style={{ color: "var(--text-secondary)", fontSize: 12 }}>{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="section-subtitle" style={{ marginTop: 12, marginBottom: 0 }}>
            この比較結果に関わらず、アプリは常に上記のルールベーススコアを使用します —
            詳細な手法は docs/ml-comparison.md を参照してください。
          </p>
        </Collapsible>
      )}
    </div>
  );
}
