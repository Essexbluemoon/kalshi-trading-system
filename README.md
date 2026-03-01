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

| Variable | Description |
|----------|-------------|
| `KALSHI_API_KEY` | Kalshi API key |
| `KALSHI_API_SECRET` | Kalshi API secret |
| `KALSHI_ENV` | `prod` or `demo` |
| `DATABASE_URL` | PostgreSQL connection string |
| `API_KEY` | Bearer token for dashboard auth |
| `POLL_INTERVAL_SECONDS` | Ingestion poll frequency (default 300) |

## Cloud Deployment (Railway)

1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.app)
3. Add a PostgreSQL plugin to the project
4. Connect your GitHub repo
5. Set environment variables in Railway dashboard (same as `.env`)
6. Railway auto-builds and serves at a public URL

Estimated cost: **$0/month** on free tier, ~$5/month at active trading volume.

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
| 2 | ⬜ Pending | Database schema + migrations |
| 2.5 | ⬜ Pending | Test suite (must pass before Phase 3) |
| 3 | ⬜ Pending | Ingestion service |
| 4 | ⬜ Pending | FastAPI backend |
| 5 | ⬜ Pending | React dashboard |
| 6 | ⬜ Pending | Integration testing |
| 7 | ⬜ Pending | Railway deployment |
