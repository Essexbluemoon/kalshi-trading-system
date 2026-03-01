"""
main.py
FastAPI application factory.
Registers all routers, configures CORS, and mounts the health endpoint.
Fully implemented in Phase 4.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Phase 4: uncomment router imports
# from routers import positions, trades, performance, categories, alerts

app = FastAPI(
    title="Kalshi Trading System API",
    description="Automated trade tracking and performance dashboard for the Longshot Fade strategy.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers (Phase 4) ──────────────────────────────────────────────────────────
# app.include_router(positions.router,   prefix="/positions",   tags=["Positions"])
# app.include_router(trades.router,      prefix="/trades",      tags=["Trades"])
# app.include_router(performance.router, prefix="/performance", tags=["Performance"])
# app.include_router(categories.router,  prefix="/categories",  tags=["Categories"])
# app.include_router(alerts.router,      prefix="/alerts",      tags=["Alerts"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
def health() -> dict:
    """Returns 200 when the API is running. Used by Railway health check."""
    return {"status": "ok", "version": app.version}
