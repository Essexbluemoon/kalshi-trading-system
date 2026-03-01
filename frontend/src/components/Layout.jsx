/**
 * Layout.jsx
 * Navigation sidebar + main content area.
 * Fully implemented in Phase 5.
 */
import React from "react";
import { NavLink, Outlet } from "react-router-dom";

const NAV_LINKS = [
  { to: "/summary",     label: "Portfolio" },
  { to: "/positions",   label: "Positions" },
  { to: "/performance", label: "Performance" },
  { to: "/trades",      label: "Trades" },
  { to: "/alerts",      label: "Alerts" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="px-6 py-5 border-b border-gray-800">
          <span className="text-sm font-semibold tracking-widest text-brand-500 uppercase">
            Kalshi
          </span>
          <p className="text-xs text-gray-500 mt-0.5">Trading Dashboard</p>
        </div>
        <nav className="flex-1 py-4 space-y-1 px-3">
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-600 text-white"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-6 py-4 border-t border-gray-800 text-xs text-gray-600">
          Phase 1 scaffold
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
