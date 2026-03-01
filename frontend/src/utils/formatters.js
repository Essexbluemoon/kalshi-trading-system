/**
 * formatters.js
 * Shared formatting utilities for currency, percentages, dates, and P&L display.
 */

/** Format a USD value with sign and 2 decimal places. e.g. +$1,234.56 */
export function fmtUsd(value, showSign = false) {
  if (value == null) return "—";
  const n = Number(value);
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(n));
  if (showSign) return (n >= 0 ? "+" : "-") + formatted;
  return n < 0 ? `-${formatted}` : formatted;
}

/** Format a decimal as a percentage. e.g. 0.9845 → "98.45%" */
export function fmtPct(value, decimals = 2) {
  if (value == null) return "—";
  return `${(Number(value) * 100).toFixed(decimals)}%`;
}

/** Format a price in cents as a cent string. e.g. 7 → "7¢" */
export function fmtCents(cents) {
  if (cents == null) return "—";
  return `${cents}¢`;
}

/** Format a UTC ISO string as a local date. e.g. "2025-03-15" */
export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

/** Format a UTC ISO string as local date + time. */
export function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/** Format a number with comma separators. */
export function fmtNumber(n, decimals = 0) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Drift color class for Tailwind.
 * Returns a text color class based on how far actual deviates from expected.
 */
export function driftColor(actual, expected) {
  if (expected == null) return "text-gray-400";
  const drift = Math.abs(Number(actual) - Number(expected));
  if (drift <= 0.02) return "text-green-400";
  if (drift <= 0.05) return "text-yellow-400";
  return "text-red-400";
}
