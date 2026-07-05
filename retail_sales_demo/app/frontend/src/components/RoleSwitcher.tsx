import type { Role } from "../types";

const ROLE_LABELS: Record<Role, string> = {
  hq: "本社経営",
  store_manager: "店長",
  merchandising: "商品企画",
  data_quality: "データ品質",
};

/**
 * これはデモの見せ方を切り替えるためのUI上の便宜であり、
 * 実際のアクセス制御（店舗別フィルタ・PIIマスキング）はサーバー側
 * （Unity Catalog行フィルタ/列マスキング、またはAPI側フィルタ）で行われる。
 * このセレクタの選択値だけで本番の権限が変わるわけではない。
 */
export function RoleSwitcher({ role, onChange }: { role: Role; onChange: (role: Role) => void }) {
  return (
    <div className="tab-bar">
      {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
        <button
          key={r}
          className={`tab-button ${r === role ? "active" : ""}`}
          onClick={() => onChange(r)}
        >
          {ROLE_LABELS[r]}
        </button>
      ))}
    </div>
  );
}
