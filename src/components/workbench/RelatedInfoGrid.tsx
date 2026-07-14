import type { RelatedInfo } from "../../types";

interface RelatedInfoGridProps {
  info: RelatedInfo;
}

const GROUPS: { key: keyof RelatedInfo; label: string }[] = [
  { key: "related_cards", label: "関連カード" },
  { key: "related_devices", label: "関連端末" },
  { key: "related_accounts", label: "関連口座" },
  { key: "related_merchants", label: "関連加盟店" },
];

function RelatedInfoGrid({ info }: RelatedInfoGridProps) {
  return (
    <section className="card" aria-labelledby="related-info-heading">
      <h2 id="related-info-heading">関連情報</h2>
      <p className="chart-caption">簡易的な関連リストです。ネットワーク分析等の高度な機能は実装していません。</p>
      <div className="related-info-grid">
        {GROUPS.map((group) => (
          <div key={group.key} className="related-info-block">
            <h3 className="chart-subheading">{group.label}</h3>
            <ul>
              {info[group.key].length === 0 ? (
                <li className="empty-state">情報なし</li>
              ) : (
                info[group.key].map((item) => <li key={item}>{item}</li>)
              )}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export default RelatedInfoGrid;
