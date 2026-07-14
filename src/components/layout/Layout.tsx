import { useState } from "react";
import { Outlet } from "react-router-dom";
import GlobalNav from "./GlobalNav";
import SyntheticDataBanner from "./SyntheticDataBanner";
import Footer from "./Footer";

export interface LayoutContext {
  setDataUpdatedAt: (value: string) => void;
}

function Layout() {
  const [dataUpdatedAt, setDataUpdatedAt] = useState<string | null>(null);

  return (
    <div className="app-shell">
      <GlobalNav dataUpdatedAt={dataUpdatedAt} />
      <SyntheticDataBanner />
      <main className="app-main">
        <Outlet context={{ setDataUpdatedAt } satisfies LayoutContext} />
      </main>
      <Footer />
    </div>
  );
}

export default Layout;
