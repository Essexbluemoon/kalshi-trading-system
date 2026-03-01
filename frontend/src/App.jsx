/**
 * App.jsx
 * Root component. Sets up React Router and renders the Layout with all panels.
 * Fully implemented in Phase 5.
 */
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";

// Phase 5: uncomment panel imports as each is built
// import PortfolioSummary  from "./components/PortfolioSummary.jsx";
// import OpenPositions     from "./components/OpenPositions.jsx";
// import Performance       from "./components/Performance.jsx";
// import CategoryBreakdown from "./components/CategoryBreakdown.jsx";
// import TradeHistory      from "./components/TradeHistory.jsx";
// import Alerts            from "./components/Alerts.jsx";

function Placeholder({ name }) {
  return (
    <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
      {name} — implemented in Phase 5
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/summary" replace />} />
          <Route path="summary"    element={<Placeholder name="Portfolio Summary" />} />
          <Route path="positions"  element={<Placeholder name="Open Positions" />} />
          <Route path="performance" element={<Placeholder name="Performance vs Benchmarks" />} />
          <Route path="trades"     element={<Placeholder name="Trade History" />} />
          <Route path="alerts"     element={<Placeholder name="Alerts" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
