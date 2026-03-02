/**
 * Performance.jsx
 * Route: /performance
 * Actual vs benchmark comparison table, per event_prefix.
 * Endpoint: GET /performance/by-category
 */
import React, { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi.js";
import { fmtUsd, fmtPct, fmtNumber } from "../utils/formatters.js";

function DriftBadge({ actual, expected }) {
  if (expected == null) return <span className="text-gray-600">—</span>;
  const drift = Math.abs(Number(actual) - Number(expected)) / Number(expected);
  let cls = "bg-green-900 text-green-300";
  if (drift > 0.10) cls = "bg-red-900 text-red-300";
  else if (drift > 0.05) cls = "bg-yellow-900 text-yellow-300";
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${cls}`}>
      {fmtPct(drift)}
    </span>
  );
}

function PnlCell({ value }) {
  if (value == null) return <span className="text-gray-600">—</span>;
  const n = Number(value);
  return (
    <span className={n >= 0 ? "text-green-400" : "text-red-400"}>
      {fmtUsd(n, true)}
    </span>
  );
}

const SORT_KEYS = ["category", "trades", "actual_win_rate", "expected_win_rate",
                   "win_rate_drift", "total_net_pnl_usd"];

export default function Performance() {
  const { data: rows, loading, error, refetch } = useApi("/performance/by-category");
  const [sortKey, setSortKey] = useState("total_net_pnl_usd");
  const [sortDir, setSortDir] = useState("desc");
  const [filterCategory, setFilterCategory] = useState("");

  function handleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  const categories = useMemo(() => {
    if (!rows) return [];
    return [...new Set(rows.map((r) => r.category).filter(Boolean))].sort();
  }, [rows]);

  const filtered = useMemo(() => {
    if (!rows) return [];
    let r = rows;
    if (filterCategory) r = r.filter((row) => row.category === filterCategory);
    return [...r].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      const cmp = typeof av === "string" ? av.localeCompare(bv) : Number(av) - Number(bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir, filterCategory]);

  function Th({ label, sortable, col, align = "right" }) {
    const active = sortKey === col;
    return (
      <th
        onClick={sortable ? () => handleSort(col) : undefined}
        className={`px-3 py-2 text-xs font-medium uppercase tracking-wider whitespace-nowrap
          ${align === "right" ? "text-right" : "text-left"}
          ${sortable ? "cursor-pointer select-none" : ""}
          ${active ? "text-brand-400" : "text-gray-500 hover:text-gray-300"}`}
      >
        {label}
        {sortable && (
          <span className="ml-1">
            {active ? (sortDir === "asc" ? "↑" : "↓") : <span className="text-gray-700">⇅</span>}
          </span>
        )}
      </th>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-white">Performance vs Benchmarks</h1>
        <div className="flex items-center gap-2">
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded px-2 py-1 focus:outline-none focus:border-brand-500"
          >
            <option value="">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button
            onClick={refetch}
            className="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-3 py-1 rounded transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm p-4 bg-red-950 border border-red-800 rounded-lg">
          Failed to load: {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-600 text-sm py-12 text-center">Loading…</div>
      ) : !error && filtered.length === 0 ? (
        <div className="text-gray-600 text-sm py-12 text-center">No data</div>
      ) : !error && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-800">
                <tr>
                  <Th label="Category"   col="category"        sortable align="left" />
                  <Th label="Subcategory" col="subcategory"    sortable={false} align="left" />
                  <Th label="Trades"     col="trades"          sortable />
                  <Th label="Actual WR"  col="actual_win_rate" sortable />
                  <Th label="Exp WR"     col="expected_win_rate" sortable />
                  <Th label="WR Drift"   col="win_rate_drift"  sortable />
                  <Th label="Net P&L"    col="total_net_pnl_usd" sortable />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {filtered.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-3 py-2 text-gray-300 whitespace-nowrap">{row.category}</td>
                    <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">
                      {row.subcategory ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-400">
                      {fmtNumber(row.trades)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {row.actual_win_rate != null ? fmtPct(row.actual_win_rate) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500">
                      {row.expected_win_rate != null ? fmtPct(row.expected_win_rate) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <DriftBadge actual={row.actual_win_rate} expected={row.expected_win_rate} />
                    </td>
                    <td className="px-3 py-2 text-right font-medium">
                      <PnlCell value={row.total_net_pnl_usd} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 border-t border-gray-800 text-xs text-gray-600">
            {filtered.length} row{filtered.length !== 1 ? "s" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
