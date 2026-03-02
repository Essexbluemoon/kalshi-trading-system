"""
run.py
Entry point for the ingestion service.
Can be called by cron or run as a persistent daemon.

Usage:
    python run.py               # run as daemon (poll every POLL_INTERVAL_SECONDS)
    python run.py --once        # run one cycle and exit (useful for cron / testing)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure api/ is importable (needed for models + database)
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi ingestion service")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingestion cycle then exit (e.g. for cron)",
    )
    args = parser.parse_args()

    from config import get_settings
    from database import SessionLocal
    from kalshi_client import KalshiClient
    from ingest_trades import run_ingestion_cycle

    settings = get_settings()

    with KalshiClient(
        api_key_id=settings.kalshi_api_key_id,
        private_key_path=settings.kalshi_private_key_path,
        env=settings.kalshi_env,
    ) as client:
        if args.once:
            logger.info("Running single ingestion cycle...")
            db = SessionLocal()
            try:
                stats = run_ingestion_cycle(db, client)
                logger.info("Done: %s", stats)
            finally:
                db.close()
        else:
            logger.info(
                "Starting ingestion daemon (interval=%ds)...",
                settings.poll_interval_seconds,
            )
            while True:
                db = SessionLocal()
                try:
                    stats = run_ingestion_cycle(db, client)
                    logger.info("Cycle complete: %s", stats)
                except Exception:
                    logger.exception("Ingestion cycle failed")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                finally:
                    db.close()

                time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
