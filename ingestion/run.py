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
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Ensure api/ is importable (needed for models + database)
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion")


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — returns 200 OK for GET /health only."""

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress per-request access logs


def _start_keepalive_pinger() -> None:
    """Ping the API /health endpoint every 4 minutes to keep it warm."""
    import urllib.request
    api_url = os.getenv("API_URL", "").rstrip("/")
    if not api_url:
        logger.info("API_URL not set — skipping keep-alive pinger")
        return
    health_url = f"{api_url}/health"
    def _ping_loop():
        while True:
            time.sleep(240)  # 4 minutes
            try:
                with urllib.request.urlopen(health_url, timeout=10) as resp:
                    logger.debug("Keep-alive ping %s → %d", health_url, resp.status)
            except Exception:
                logger.warning("Keep-alive ping to %s failed", health_url, exc_info=True)
    thread = threading.Thread(target=_ping_loop, daemon=True)
    thread.start()
    logger.info("Keep-alive pinger started → %s every 4m", health_url)


def _start_health_server() -> None:
    """Start a lightweight HTTP health server in a background daemon thread."""
    port = int(os.getenv("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on port %d", port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi ingestion service")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingestion cycle then exit (e.g. for cron)",
    )
    args = parser.parse_args()

    _start_health_server()
    _start_keepalive_pinger()

    from config import get_settings
    from database import SessionLocal
    from kalshi_client import KalshiClient
    from ingest_trades import run_ingestion_cycle

    settings = get_settings()

    if args.once:
        with KalshiClient(
            api_key_id=settings.kalshi_api_key_id,
            private_key_path=settings.kalshi_private_key_path,
            env=settings.kalshi_env,
        ) as client:
            logger.info("Running single ingestion cycle...")
            db = SessionLocal()
            try:
                stats = run_ingestion_cycle(db, client)
                logger.info("Done: %s", stats)
            finally:
                db.close()
        return

    # ── Daemon mode — outer loop ensures the process never exits normally ──────
    logger.info(
        "Starting ingestion daemon (interval=%ds)...",
        settings.poll_interval_seconds,
    )
    while True:
        try:
            with KalshiClient(
                api_key_id=settings.kalshi_api_key_id,
                private_key_path=settings.kalshi_private_key_path,
                env=settings.kalshi_env,
            ) as client:
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
        except Exception:
            logger.exception("Daemon error — reconnecting in 60s")
            time.sleep(60)


if __name__ == "__main__":
    while True:
        try:
            main()
            break  # --once completed normally; exit cleanly
        except SystemExit:
            raise  # honour explicit sys.exit() calls (e.g. argparse --help)
        except BaseException:
            logger.exception("Fatal error at top level — restarting in 60s")
            time.sleep(60)
