import { HashRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DailyKpiDashboard } from "./pages/DailyKpiDashboard";
import { DataQualitySummary } from "./pages/DataQualitySummary";
import { FailedPaymentUsers } from "./pages/FailedPaymentUsers";
import { SalesPerPlan } from "./pages/SalesPerPlan";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DailyKpiDashboard />} />
          <Route path="sales-per-plan" element={<SalesPerPlan />} />
          <Route path="failed-payment-users" element={<FailedPaymentUsers />} />
          <Route path="data-quality" element={<DataQualitySummary />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
