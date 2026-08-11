"""Optional in-process market sync — lets a single free-tier web service keep
its live markets fresh without a separate (paid) cron worker.

Enabled by setting SYNC_INTERVAL_MINUTES > 0. The API's lifespan starts one
background asyncio task that runs the same reconciliation pass as
scripts/sync_markets.py on that interval: add/refresh active markets, record
price ticks, deactivate stale listings, and settle resolved markets. The pass
runs in a worker thread so it never blocks the event loop.

Deterministic, play-money only — nothing here moves real money.
"""

import asyncio
import logging
import os
from argparse import Namespace

logger = logging.getLogger("vanta.sync")


def _sync_args() -> Namespace:
    """A modest pass sized for a background loop on a small instance."""
    return Namespace(
        polymarket_pages=int(os.environ.get("SYNC_POLYMARKET_PAGES", "10")),
        kalshi_pages=int(os.environ.get("SYNC_KALSHI_PAGES", "1")),
        manifold_pages=int(os.environ.get("SYNC_MANIFOLD_PAGES", "1")),
        stale_hours=24.0,
        settle=True,
    )


def _run_one_pass() -> None:
    # Imported lazily: the sync module binds DATABASE_URL from the environment
    # the API already set, and pulls in venue clients only when actually used.
    from scripts.sync_markets import run_pass

    from .db import SessionLocal

    with SessionLocal() as session:
        run_pass(session, _sync_args())


async def _loop(interval_minutes: float) -> None:
    # A short initial delay lets the app finish booting (and seeding) first.
    await asyncio.sleep(15)
    while True:
        try:
            await asyncio.to_thread(_run_one_pass)
        except Exception:  # a venue hiccup must never kill the loop
            logger.exception("background market sync pass failed")
        await asyncio.sleep(interval_minutes * 60)


def start_background_sync() -> asyncio.Task | None:
    """Start the periodic sync task if SYNC_INTERVAL_MINUTES is set (>0).
    Returns the task (so the caller can cancel it on shutdown) or None."""
    try:
        interval = float(os.environ.get("SYNC_INTERVAL_MINUTES", "0"))
    except ValueError:
        interval = 0
    if interval <= 0:
        return None
    logger.info("starting in-process market sync every %.0f min", interval)
    return asyncio.create_task(_loop(interval))
