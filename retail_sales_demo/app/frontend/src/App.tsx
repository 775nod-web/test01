import { useState } from "react";
import type { Role } from "./types";
import { RoleSwitcher } from "./components/RoleSwitcher";
import { HeadOfficeDashboard } from "./pages/HeadOfficeDashboard";
import { StoreView } from "./pages/StoreView";
import { MerchandisingView } from "./pages/MerchandisingView";
import { DataQualityView } from "./pages/DataQualityView";

const VIEWS: Record<Role, () => JSX.Element> = {
  hq: HeadOfficeDashboard,
  store_manager: StoreView,
  merchandising: MerchandisingView,
  data_quality: DataQualityView,
};

export function App() {
  const [role, setRole] = useState<Role>("hq");
  const ActiveView = VIEWS[role];

  return (
    <div className="app-shell">
      <h1>小売POS売上分析デモ</h1>
      <RoleSwitcher role={role} onChange={setRole} />
      <ActiveView />
    </div>
  );
}
