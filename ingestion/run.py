"""
run.py
Entry point for the ingestion service.
Can be called by cron or run as a persistent daemon.

Usage:
    python run.py               # run as daemon (poll every POLL_INTERVAL_SECONDS)
    python run.py --once        # run one cycle and exit (useful for cron / testing)

Full implementation in Phase 3.
"""
from __future__ import annotations

import argparse
import logging
import time

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
        help="Run a single ingestion cycle then exit",
    )
    args = parser.parse_args()

    # Phase 3: initialise settings, db session, kalshi client
    # settings = get_settings()
    # db = get_db_session(settings.database_url)
    # client = KalshiClient(settings.kalshi_api_key, settings.kalshi_api_secret, settings.kalshi_env)

    if args.once:
        logger.info("Running single ingestion cycle...")
        # run_ingestion_cycle(db, client)
        raise NotImplementedError("Implemented in Phase 3")
    else:
        logger.info("Starting ingestion daemon...")
        while True:
            try:
                # run_ingestion_cycle(db, client)
                raise NotImplementedError("Implemented in Phase 3")
            except Exception:
                logger.exception("Ingestion cycle failed")
            # time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
