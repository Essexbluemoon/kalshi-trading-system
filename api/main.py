"""
main.py
FastAPI application factory.
Registers all routers, configures CORS, and mounts the health endpoint.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make ingestion/ importable so routers can call run_reconcile + position_manager.
# In Docker, the api container mounts ./ingestion at /app/ingestion (docker-compose.yml).
_INGESTION_DIR = Path(__file__).parent.parent / "ingestion"
if _INGESTION_DIR.exists():
    sys.path.insert(0, str(_INGESTION_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import positions, trades, performance, categories, alerts, benchmarks

app = FastAPI(
    title="Kalshi Trading System API",
    description="Automated trade tracking and performance dashboard for the Longshot Fade strategy.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(positions.router,   prefix="/positions",   tags=["Positions"])
app.include_router(trades.router,      prefix="/trades",      tags=["Trades"])
app.include_router(performance.router, prefix="/performance", tags=["Performance"])
app.include_router(categories.router,  prefix="/categories",  tags=["Categories"])
app.include_router(alerts.router,      prefix="/alerts",      tags=["Alerts"])
app.include_router(benchmarks.router,  prefix="/benchmarks",  tags=["Benchmarks"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["Meta"])
def health() -> dict:
    """Returns 200 when the API is running. Used by Railway health check."""
    return {"status": "ok", "version": app.version}
