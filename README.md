# Kalshi Trading System

Automated trade ingestion, performance tracking, and dashboard for the Longshot Fade strategy.

## Architecture

| Layer | Technology | Port |
|-------|-----------|------|
| Database | PostgreSQL 15 | 5432 |
| Backend API | FastAPI (Python) | 8000 |
| Frontend | React + Tailwind CSS | 3000 |
| Ingestion | Python daemon | — |

## Quick Start (Local Development)

### Prerequisites

- Docker Desktop installed and running
- Git

### 1. Clone and configure

```bash
git clone <your-repo-url> kalshi-trading-system
cd kalshi-trading-system
cp .env.example .env
# Edit .env and fill in your Kalshi API credentials and API_KEY
```

### 2. Start all services

```bash
docker-compose up
```

This starts PostgreSQL, the FastAPI backend, the React frontend, and the ingestion service in the correct order.

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| API docs (Redoc) | http://localhost:8000/redoc |

### 3. Run database migrations

On first run, apply the schema:

```bash
docker-compose exec api python scripts/migrate.py
```

### 4. Import benchmarks

Populate the benchmarks table from the Becker backtest output:

```bash
docker-compose exec api python scripts/import_benchmarks.py ../benchmarks/
```

### 5. Seed with sandbox data (optional)

Set `KALSHI_ENV=demo` in `.env`, then trigger a manual ingestion run:

```bash
docker-compose exec ingestion python run.py --once
```

## Repository Structure

```
kalshi-trading-system/
├── ingestion/              # Trade ingestion service (Python daemon)
│   ├── config.py           # Env vars, DB URL, API credentials
│   ├── kalshi_client.py    # pykalshi API wrapper
│   ├── ingest_trades.py    # Main ingestion loop
│   ├── ingest_markets.py   # Market metadata + resolution fetcher
│   ├── position_manager.py # Trade → position aggregation + P&L
│   ├── reconcile.py        # Benchmark drift alerts
│   └── run.py              # Entry point (cron or daemon)
├── api/                    # FastAPI backend
│   ├── main.py             # App factory, CORS, router registration
│   ├── database.py         # SQLAlchemy engine + session
│   ├── models.py           # ORM models
│   ├── schemas.py          # Pydantic response models
│   ├── auth.py             # API key middleware
│   └── routers/            # One file per endpoint group
├── frontend/               # React dashboard
│   └── src/
│       ├── App.jsx
│       ├── components/     # Dashboard panels
│       ├── hooks/          # useApi shared hook
│       └── utils/          # Formatters
├── benchmarks/             # Becker backtest CSV files (input only)
├── scripts/                # DB migration, benchmark import, utilities
├── tests/                  # pytest suite (must pass before Phase 3)
├── docker-compose.yml      # Local dev orchestration
├── railway.toml            # Railway cloud deployment config
└── .env.example            # Environment variable template
```

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Service | Description |
|----------|---------|-------------|
| `KALSHI_API_KEY_ID` | Ingestion | Key ID from Kalshi dashboard |
| `KALSHI_PRIVATE_KEY` | Ingestion | Full PEM content (Railway/cloud) |
| `KALSHI_PRIVATE_KEY_PATH` | Ingestion | Path to PEM file (local dev) |
| `KALSHI_ENV` | Ingestion | `prod` or `demo` |
| `DATABASE_URL` | API + Ingestion | PostgreSQL connection string |
| `API_KEY` | API + Ingestion | Bearer token for dashboard auth |
| `POLL_INTERVAL_SECONDS` | Ingestion | Poll frequency (default 300) |
| `CORS_ORIGINS` | API | Comma-separated allowed origins |
| `API_UPSTREAM` | Frontend | Internal API URL for nginx proxy |

## Cloud Deployment (Railway)

### Prerequisites

- Repo pushed to GitHub
- [Railway](https://railway.app) account

### Step 1 — Create project and add PostgreSQL

1. Create a new Railway project
2. Click **+ New** → **Database** → **PostgreSQL**
3. Railway will auto-inject `DATABASE_URL` into any service that references it

### Step 2 — Add API service

1. Click **+ New** → **GitHub Repo** → select your repo
2. Railway will auto-detect `Dockerfile` at the repo root
3. Set environment variables:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | (reference the PostgreSQL plugin variable) |
| `API_KEY` | your secret bearer token |
| `CORS_ORIGINS` | `https://<your-frontend>.up.railway.app` |

### Step 3 — Add Ingestion worker

1. Click **+ New** → **GitHub Repo** → same repo
2. In service settings → **Source** → set:
   - Root directory: `/`
   - Dockerfile path: `Dockerfile.ingestion`
3. Set environment variables:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | (reference the PostgreSQL plugin variable) |
| `KALSHI_API_KEY_ID` | from Kalshi dashboard |
| `KALSHI_PRIVATE_KEY` | paste full PEM file contents |
| `KALSHI_ENV` | `prod` or `demo` |
| `POLL_INTERVAL_SECONDS` | `300` |
| `API_KEY` | same as API service |

### Step 4 — Add Frontend service

1. Click **+ New** → **GitHub Repo** → same repo
2. In service settings → **Source** → set:
   - Root directory: `/frontend`
   - Build target: `prod`
3. Set environment variables:

| Variable | Value |
|----------|-------|
| `API_UPSTREAM` | `http://api.railway.internal:8000` |

### Step 5 — Deploy

Push a commit to `main`; Railway auto-deploys all four services.

Verify with `GET /health` on the API service URL.

Estimated cost: **~$5/month** at active trading volume (PostgreSQL + 3 services).

## API Reference

With the API running, full interactive docs are available at:
- Swagger UI: http://localhost:8000/docs
- Redoc: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/positions` | All open positions with unrealized P&L |
| GET | `/performance/summary` | Overall P&L, win rate, Sharpe vs benchmarks |
| GET | `/performance/by-category` | Per-category vs Becker benchmarks |
| GET | `/alerts` | Active drift alerts and warnings |
| GET | `/benchmarks` | Full benchmark table |

All endpoints require `Authorization: Bearer <API_KEY>` header.

## Development Notes

- P&L calculations use the **maker fee formula**: `0.0175 × contracts × (price/100) × (1 - price/100)`
- All prices stored in cents (integer 1–99) matching Kalshi's native format
- All timestamps UTC
- Category classification mirrors the Becker backtest prefix mapping

## Build Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Project scaffold |
| 2 | ✅ Complete | Database schema + migrations |
| 2.5 | ✅ Complete | Test suite (87 passing) |
| 3 | ✅ Complete | Ingestion service |
| 4 | ✅ Complete | FastAPI backend |
| 5 | ✅ Complete | React dashboard |
| 6 | ✅ Complete | Integration testing |
| 7 | ✅ Complete | Railway deployment |
