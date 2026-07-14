import type { Channel, Period, Scenario } from "../../types";

interface FilterBarProps {
  period: Period;
  scenario: Scenario;
  channel: Channel;
  onChange: (next: { period: Period; scenario: Scenario; channel: Channel }) => void;
}

function FilterBar({ period, scenario, channel, onChange }: FilterBarProps) {
  return (
    <div className="filter-bar" role="group" aria-label="ダッシュボードのフィルター">
      <div className="filter-field">
        <label htmlFor="filter-period">期間</label>
        <select
          id="filter-period"
          value={period}
          onChange={(e) => onChange({ period: e.target.value as Period, scenario, channel })}
        >
          <option value="7d">過去7日</option>
          <option value="30d">過去30日</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="filter-scenario">判定方式</label>
        <select
          id="filter-scenario"
          value={scenario}
          onChange={(e) => onChange({ period, scenario: e.target.value as Scenario, channel })}
        >
          <option value="rules">既存ルールのみ</option>
          <option value="hybrid">ルール＋AI</option>
        </select>
      </div>

      <div className="filter-field">
        <label htmlFor="filter-channel">チャネル</label>
        <select
          id="filter-channel"
          value={channel}
          onChange={(e) => onChange({ period, scenario, channel: e.target.value as Channel })}
        >
          <option value="all">すべて</option>
          <option value="mobile">モバイル決済</option>
          <option value="debit">デビットカード</option>
        </select>
      </div>
    </div>
  );
}

export default FilterBar;
