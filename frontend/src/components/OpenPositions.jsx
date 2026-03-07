/**
 * OpenPositions.jsx
 * Route: /positions
 * Sortable table of open positions with unrealized P&L and expected EV.
 * Endpoint: GET /positions/
 */
import React, { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi.js";
import { fmtUsd, fmtCents, fmtNumber, fmtDate } from "../utils/formatters.js";

const COLUMNS = [
  { key: "market_ticker",      label: "Ticker",       align: "left"  },
  { key: "category",           label: "Category",     align: "left"  },
  { key: "side",               label: "Side",         align: "left"  },
  { key: "net_contracts",      label: "Contracts",    align: "right" },
  { key: "avg_price_cents",    label: "Avg Price",    align: "right" },
  { key: "total_cost_usd",     label: "Cost",         align: "right" },
  { key: "unrealized_pnl_usd", label: "Unreal. P&L", align: "right" },
  { key: "expected_ev_per_ctr",label: "Exp EV/ctr",  align: "right" },
  { key: "days_open",          label: "Days Open",    align: "right" },
  { key: "opened_at",          label: "Opened",       align: "right" },
];

function SortIcon({ dir }) {
  if (!dir) return <span className="text-gray-700 ml-1">⇅</span>;
  return <span className="text-brand-500 ml-1">{dir === "asc" ? "↑" : "↓"}</span>;
}

function Th({ col, sortKey, sortDir, onSort }) {
  const active = sortKey === col.key;
  return (
    <th
      onClick={() => onSort(col.key)}
      className={`px-3 py-2 text-xs font-medium uppercase tracking-wider cursor-pointer select-none whitespace-nowrap
        ${col.align === "right" ? "text-right" : "text-left"}
        ${active ? "text-brand-400" : "text-gray-500 hover:text-gray-300"}`}
    >
      {col.label}
      <SortIcon dir={active ? sortDir : null} />
    </th>
  );
}

export default function OpenPositions() {
  const { data: positions, loading, error, refetch } = useApi("/positions/");
  const [sortKey, setSortKey] = useState("unrealized_pnl_usd");
  const [sortDir, setSortDir] = useState("desc");

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sorted = useMemo(() => {
    if (!positions) return [];
    return [...positions].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      const cmp = typeof av === "string" ? av.localeCompare(bv) : Number(av) - Number(bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [positions, sortKey, sortDir]);

  function pnlClass(val) {
    if (val == null) return "text-gray-400";
    return Number(val) >= 0 ? "text-green-400" : "text-red-400";
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Open Positions</h1>
        <button
          onClick={refetch}
          className="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 hover:border-gray-500 px-3 py-1 rounded transition-colors"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="text-red-400 text-sm p-4 bg-red-950 border border-red-800 rounded-lg">
          Failed to load: {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-600 text-sm py-12 text-center">Loading…</div>
      ) : !error && sorted.length === 0 ? (
        <div className="text-gray-600 text-sm py-12 text-center">No open positions</div>
      ) : !error && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-800">
                <tr>
                  {COLUMNS.map((col) => (
                    <Th key={col.key} col={col} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.map((pos) => (
                  <tr key={pos.market_ticker} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-3 py-2 font-mono text-xs text-gray-300 whitespace-nowrap">
                      {pos.market_ticker}
                    </td>
                    <td className="px-3 py-2 text-gray-400 whitespace-nowrap">
                      {pos.category ?? <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded ${
                        pos.side === "yes"
                          ? "bg-blue-900 text-blue-300"
                          : "bg-orange-900 text-orange-300"
                      }`}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {fmtNumber(pos.net_contracts)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {fmtCents(pos.side === "no" ? 100 - pos.avg_price_cents : pos.avg_price_cents)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {fmtUsd(pos.total_cost_usd)}
                    </td>
                    <td className={`px-3 py-2 text-right font-medium ${pnlClass(pos.unrealized_pnl_usd)}`}>
                      {fmtUsd(pos.unrealized_pnl_usd, true)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-400">
                      {pos.expected_ev_per_ctr != null
                        ? fmtUsd(pos.expected_ev_per_ctr)
                        : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-400">
                      {pos.days_open != null ? `${pos.days_open}d` : "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500 text-xs whitespace-nowrap">
                      {fmtDate(pos.opened_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 border-t border-gray-800 text-xs text-gray-600">
            {sorted.length} position{sorted.length !== 1 ? "s" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
