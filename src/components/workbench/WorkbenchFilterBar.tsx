import type { CaseListParams } from "../../api";

interface WorkbenchFilterBarProps {
  filters: CaseListParams;
  onChange: (next: CaseListParams) => void;
}

function WorkbenchFilterBar({ filters, onChange }: WorkbenchFilterBarProps) {
  return (
    <div className="filter-bar" role="group" aria-label="調査ケースのフィルター">
      <div className="filter-field">
        <label htmlFor="filter-priority">優先度</label>
        <select
          id="filter-priority"
          value={filters.priority ?? ""}
          onChange={(e) => onChange({ ...filters, priority: (e.target.value || undefined) as CaseListParams["priority"] })}
        >
          <option value="">すべて</option>
          <option value="最優先">最優先</option>
          <option value="高">高</option>
          <option value="中">中</option>
          <option value="低">低</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="filter-status">ステータス</label>
        <select
          id="filter-status"
          value={filters.status ?? ""}
          onChange={(e) => onChange({ ...filters, status: (e.target.value || undefined) as CaseListParams["status"] })}
        >
          <option value="">すべて</option>
          <option value="未着手">未着手</option>
          <option value="調査中">調査中</option>
          <option value="完了">完了</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="filter-action">推奨アクション</label>
        <select
          id="filter-action"
          value={filters.recommended_action ?? ""}
          onChange={(e) =>
            onChange({ ...filters, recommended_action: (e.target.value || undefined) as CaseListParams["recommended_action"] })
          }
        >
          <option value="">すべて</option>
          <option value="承認">承認</option>
          <option value="ステップアップ認証">ステップアップ認証</option>
          <option value="保留">保留</option>
          <option value="拒否">拒否</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="filter-risk-band">リスクスコア帯</label>
        <select
          id="filter-risk-band"
          value={filters.risk_band ?? ""}
          onChange={(e) => onChange({ ...filters, risk_band: (e.target.value || undefined) as CaseListParams["risk_band"] })}
        >
          <option value="">すべて</option>
          <option value="低">低</option>
          <option value="中">中</option>
          <option value="高">高</option>
        </select>
      </div>

      <div className="filter-field filter-field-grow">
        <label htmlFor="filter-query">フリーテキスト検索</label>
        <input
          id="filter-query"
          type="search"
          placeholder="取引ID または 加盟店名"
          value={filters.q ?? ""}
          onChange={(e) => onChange({ ...filters, q: e.target.value || undefined })}
        />
      </div>
    </div>
  );
}

export default WorkbenchFilterBar;
