import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { CustomerDetail } from "./pages/CustomerDetail";
import { ExecutiveOverview } from "./pages/ExecutiveOverview";
import { PocFutureExpansion } from "./pages/PocFutureExpansion";
import { RetentionActions } from "./pages/RetentionActions";
import { SegmentExplorer } from "./pages/SegmentExplorer";

export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<ExecutiveOverview />} />
          <Route path="/segments" element={<SegmentExplorer />} />
          <Route path="/customers/:customerId" element={<CustomerDetail />} />
          <Route path="/retention-actions" element={<RetentionActions />} />
          <Route path="/poc" element={<PocFutureExpansion />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}
