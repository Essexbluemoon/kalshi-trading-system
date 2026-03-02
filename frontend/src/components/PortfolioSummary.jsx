/**
 * PortfolioSummary.jsx
 * Route: /summary
 * Four stat cards + cumulative realized P&L line chart.
 * Endpoints: GET /performance/summary, GET /performance/daily
 */
import React, { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { useApi } from "../hooks/useApi.js";
import { fmtUsd, fmtPct, fmtNumber, fmtDate } from "../utils/formatters.js";

function StatCard({ label, value, sub, valueClass = "text-white" }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-semibold ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

function LoadError({ error }) {
  return (
    <div className="text-red-400 text-sm p-4 bg-red-950 border border-red-800 rounded-lg">
      Failed to load: {error}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm shadow-xl">
      <p className="text-gray-400 mb-1">{label}</p>
      <p className={`font-semibold ${val >= 0 ? "text-green-400" : "text-red-400"}`}>
        {fmtUsd(val, true)}
      </p>
    </div>
  );
}

export default function PortfolioSummary() {
  const { data: summary, loading: sLoading, error: sError } = useApi("/performance/summary");
  const { data: daily,   loading: dLoading, error: dError   } = useApi("/performance/daily");

  const chartData = useMemo(() => {
    if (!daily) return [];
    let cumulative = 0;
    return daily.map((row) => {
      cumulative += Number(row.net_pnl_usd);
      return { date: fmtDate(row.date), cumPnl: Math.round(cumulative * 100) / 100 };
    });
  }, [daily]);

  const lastCum = chartData.length ? chartData[chartData.length - 1].cumPnl : 0;
  const lineColor = lastCum >= 0 ? "#4ade80" : "#f87171";

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-white">Portfolio Summary</h1>

      {sError ? <LoadError error={sError} /> : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Capital Deployed"
            value={sLoading ? "…" : fmtUsd(summary?.total_capital_deployed_usd)}
          />
          <StatCard
            label="Unrealized P&L"
            value={sLoading ? "…" : fmtUsd(summary?.unrealized_pnl_usd, true)}
            valueClass={
              !summary ? "text-white"
              : Number(summary.unrealized_pnl_usd) >= 0 ? "text-green-400" : "text-red-400"
            }
          />
          <StatCard
            label="Realized P&L"
            value={sLoading ? "…" : fmtUsd(summary?.realized_pnl_usd, true)}
            valueClass={
              !summary ? "text-white"
              : Number(summary.realized_pnl_usd) >= 0 ? "text-green-400" : "text-red-400"
            }
            sub={
              sLoading || !summary ? null
              : `${fmtNumber(summary.total_wins)}W / ${fmtNumber(summary.total_losses)}L`
            }
          />
          <StatCard
            label="Win Rate"
            value={sLoading ? "…" : fmtPct(summary?.win_rate)}
            sub={sLoading || !summary ? null : `${fmtNumber(summary.total_settled)} settled`}
          />
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-sm font-medium text-gray-400 mb-4">Cumulative Realized P&L</h2>
        {dError ? <LoadError error={dError} /> : dLoading ? (
          <div className="h-56 flex items-center justify-center text-gray-600 text-sm">Loading…</div>
        ) : chartData.length === 0 ? (
          <div className="h-56 flex items-center justify-center text-gray-600 text-sm">
            No daily performance data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                tickLine={false}
                axisLine={{ stroke: "#374151" }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#6b7280" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => fmtUsd(v)}
                width={76}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="cumPnl"
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: lineColor }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
