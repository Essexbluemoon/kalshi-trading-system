/**
 * TradeHistory.jsx
 * Route: /trades
 * Filterable trade fill log.
 * Endpoint: GET /trades/?start_date=&end_date=&category=&strategy=&won=
 */
import React, { useState, useCallback } from "react";
import { useApi } from "../hooks/useApi.js";
import { fmtUsd, fmtCents, fmtNumber, fmtDateTime } from "../utils/formatters.js";

function buildQuery(filters) {
  const params = new URLSearchParams();
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date)   params.set("end_date",   filters.end_date);
  if (filters.category)   params.set("category",   filters.category);
  if (filters.strategy)   params.set("strategy",   filters.strategy);
  if (filters.won !== "")  params.set("won",        filters.won);
  params.set("limit", "500");
  const qs = params.toString();
  return `/trades/${qs ? "?" + qs : ""}`;
}

const EMPTY_FILTERS = {
  start_date: "", end_date: "", category: "", strategy: "", won: "",
};

export default function TradeHistory() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [path, setPath] = useState("/trades/");

  const { data: trades, loading, error, refetch } = useApi(path);

  function handleChange(e) {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  }

  function handleApply(e) {
    e.preventDefault();
    const newPath = buildQuery(filters);
    setApplied(filters);
    if (newPath === path) refetch();
    else setPath(newPath);
  }

  function handleReset() {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPath("/trades/");
  }

  const inputCls = "bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded px-2 py-1 focus:outline-none focus:border-brand-500 w-full";

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Trade History</h1>

      {/* Filter bar */}
      <form
        onSubmit={handleApply}
        className="bg-gray-900 border border-gray-800 rounded-xl p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end"
      >
        <div>
          <label className="block text-xs text-gray-500 mb-1">Start date</label>
          <input type="date" name="start_date" value={filters.start_date} onChange={handleChange} className={inputCls} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">End date</label>
          <input type="date" name="end_date" value={filters.end_date} onChange={handleChange} className={inputCls} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Category</label>
          <input type="text" name="category" placeholder="e.g. Sports" value={filters.category} onChange={handleChange} className={inputCls} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Strategy</label>
          <input type="text" name="strategy" placeholder="e.g. longshot_fade" value={filters.strategy} onChange={handleChange} className={inputCls} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Result</label>
          <select name="won" value={filters.won} onChange={handleChange} className={inputCls}>
            <option value="">All</option>
            <option value="true">Won</option>
            <option value="false">Lost</option>
          </select>
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            className="flex-1 bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium py-1 rounded transition-colors"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={handleReset}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm py-1 rounded transition-colors"
          >
            Reset
          </button>
        </div>
      </form>

      {error && (
        <div className="text-red-400 text-sm p-4 bg-red-950 border border-red-800 rounded-lg">
          Failed to load: {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-600 text-sm py-12 text-center">Loading…</div>
      ) : !error && (!trades || trades.length === 0) ? (
        <div className="text-gray-600 text-sm py-12 text-center">No trades match your filters</div>
      ) : !error && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-800">
                <tr>
                  {[
                    ["Filled At",   "text-left"],
                    ["Ticker",      "text-left"],
                    ["Side",        "text-left"],
                    ["Action",      "text-left"],
                    ["Contracts",   "text-right"],
                    ["Price",       "text-right"],
                    ["Gross Cost",  "text-right"],
                    ["Fee",         "text-right"],
                    ["Strategy",    "text-left"],
                  ].map(([label, align]) => (
                    <th
                      key={label}
                      className={`px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider ${align} whitespace-nowrap`}
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {trades.map((t) => (
                  <tr key={t.trade_id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">
                      {fmtDateTime(t.filled_at)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-300 whitespace-nowrap">
                      {t.market_ticker}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded ${
                        t.side === "yes"
                          ? "bg-blue-900 text-blue-300"
                          : "bg-orange-900 text-orange-300"
                      }`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-gray-400">{t.action}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{fmtNumber(t.contracts)}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{fmtCents(t.price_cents)}</td>
                    <td className="px-3 py-2 text-right text-gray-300">{fmtUsd(t.gross_cost_usd)}</td>
                    <td className="px-3 py-2 text-right text-gray-500">{fmtUsd(t.fee_usd)}</td>
                    <td className="px-3 py-2 text-gray-600 text-xs">{t.strategy ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 border-t border-gray-800 text-xs text-gray-600">
            {trades.length} fill{trades.length !== 1 ? "s" : ""} shown (max 500)
          </div>
        </div>
      )}
    </div>
  );
}
