/**
 * App.jsx
 * Root component. Sets up React Router and renders the Layout with all panels.
 */
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout           from "./components/Layout.jsx";
import PortfolioSummary from "./components/PortfolioSummary.jsx";
import OpenPositions    from "./components/OpenPositions.jsx";
import TradeHistory     from "./components/TradeHistory.jsx";
import Alerts           from "./components/Alerts.jsx";
import Performance      from "./components/Performance.jsx";
import CategoryBreakdown from "./components/CategoryBreakdown.jsx";

function PerformancePage() {
  return (
    <div>
      <Performance />
      <CategoryBreakdown />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/summary" replace />} />
          <Route path="summary"     element={<PortfolioSummary />} />
          <Route path="positions"   element={<OpenPositions />} />
          <Route path="performance" element={<PerformancePage />} />
          <Route path="trades"      element={<TradeHistory />} />
          <Route path="alerts"      element={<Alerts />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
