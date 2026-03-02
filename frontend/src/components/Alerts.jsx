/**
 * Alerts.jsx
 * Route: /alerts
 * Active alert cards from reconcile.py, severity-coloured.
 * Endpoint: GET /alerts/
 */
import React from "react";
import { useApi } from "../hooks/useApi.js";
import { fmtDateTime } from "../utils/formatters.js";

const SEVERITY_STYLES = {
  critical: {
    border: "border-red-700",
    badge:  "bg-red-900 text-red-300",
    icon:   "🔴",
  },
  warning: {
    border: "border-yellow-700",
    badge:  "bg-yellow-900 text-yellow-300",
    icon:   "🟡",
  },
  info: {
    border: "border-blue-700",
    badge:  "bg-blue-900 text-blue-300",
    icon:   "🔵",
  },
};

function severityStyle(severity) {
  return SEVERITY_STYLES[severity?.toLowerCase()] ?? SEVERITY_STYLES.info;
}

function AlertCard({ alert }) {
  const style = severityStyle(alert.severity);
  return (
    <div className={`bg-gray-900 border ${style.border} rounded-xl p-4 space-y-2`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span>{style.icon}</span>
          <span className="text-sm font-semibold text-gray-100">{alert.title}</span>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded ${style.badge}`}>
          {alert.severity}
        </span>
      </div>

      <p className="text-sm text-gray-400 leading-relaxed">{alert.message}</p>

      <div className="flex items-center gap-4 text-xs text-gray-600">
        {alert.alert_type && (
          <span className="font-mono bg-gray-800 px-1.5 py-0.5 rounded">{alert.alert_type}</span>
        )}
        {alert.category && <span>{alert.category}</span>}
        {alert.market_ticker && (
          <span className="font-mono text-gray-500">{alert.market_ticker}</span>
        )}
        {alert.created_at && <span>{fmtDateTime(alert.created_at)}</span>}
      </div>
    </div>
  );
}

export default function Alerts() {
  const { data: alerts, loading, error, refetch } = useApi("/alerts/");

  const grouped = alerts
    ? {
        critical: alerts.filter((a) => a.severity?.toLowerCase() === "critical"),
        warning:  alerts.filter((a) => a.severity?.toLowerCase() === "warning"),
        info:     alerts.filter((a) => !["critical", "warning"].includes(a.severity?.toLowerCase())),
      }
    : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Alerts</h1>
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
        <div className="text-gray-600 text-sm py-12 text-center">Running reconcile checks…</div>
      ) : !error && alerts?.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-2xl mb-2">✅</p>
          <p className="text-gray-400 text-sm">All checks passed — no active alerts</p>
        </div>
      ) : !error && grouped && (
        <div className="space-y-6">
          {grouped.critical.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-red-400 mb-2">
                Critical ({grouped.critical.length})
              </h2>
              <div className="space-y-3">
                {grouped.critical.map((a, i) => <AlertCard key={i} alert={a} />)}
              </div>
            </section>
          )}
          {grouped.warning.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-yellow-400 mb-2">
                Warnings ({grouped.warning.length})
              </h2>
              <div className="space-y-3">
                {grouped.warning.map((a, i) => <AlertCard key={i} alert={a} />)}
              </div>
            </section>
          )}
          {grouped.info.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-2">
                Info ({grouped.info.length})
              </h2>
              <div className="space-y-3">
                {grouped.info.map((a, i) => <AlertCard key={i} alert={a} />)}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
