/**
 * CategoryBreakdown.jsx
 * Embedded on the /performance route (below the Performance table).
 * Per-category cards showing benchmark count, settled trades,
 * actual win rate vs expected, and total net P&L.
 * Endpoint: GET /categories/
 */
import React from "react";
import { useApi } from "../hooks/useApi.js";
import { fmtUsd, fmtPct, fmtNumber, driftColor } from "../utils/formatters.js";

function CategoryCard({ row }) {
  const wr_class = driftColor(row.actual_win_rate, row.avg_expected_wr);
  const pnlPositive = Number(row.total_net_pnl_usd) >= 0;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-200 leading-tight">{row.category}</p>
        <span className={`text-xs font-semibold whitespace-nowrap ${pnlPositive ? "text-green-400" : "text-red-400"}`}>
          {fmtUsd(row.total_net_pnl_usd, true)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-gray-500">Benchmarks</span>
        <span className="text-right text-gray-300">{fmtNumber(row.benchmark_count)}</span>

        <span className="text-gray-500">Settled trades</span>
        <span className="text-right text-gray-300">{fmtNumber(row.settled_trades)}</span>

        <span className="text-gray-500">Actual WR</span>
        <span className={`text-right font-medium ${row.actual_win_rate != null ? wr_class : "text-gray-600"}`}>
          {row.actual_win_rate != null ? fmtPct(row.actual_win_rate) : "—"}
        </span>

        <span className="text-gray-500">Expected WR</span>
        <span className="text-right text-gray-400">
          {row.avg_expected_wr != null ? fmtPct(row.avg_expected_wr) : "—"}
        </span>
      </div>
    </div>
  );
}

export default function CategoryBreakdown() {
  const { data: categories, loading, error } = useApi("/categories/");

  return (
    <div className="space-y-4 mt-8">
      <h2 className="text-lg font-semibold text-white">Category Breakdown</h2>

      {error && (
        <div className="text-red-400 text-sm p-4 bg-red-950 border border-red-800 rounded-lg">
          Failed to load: {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-600 text-sm py-8 text-center">Loading…</div>
      ) : !error && (!categories || categories.length === 0) ? (
        <div className="text-gray-600 text-sm py-8 text-center">No categories found</div>
      ) : !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {categories.map((row) => (
            <CategoryCard key={row.category} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
