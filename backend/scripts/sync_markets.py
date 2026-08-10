"""Sync the live play-money trading surface with the venues' current listings.

One pass, stateless by design (no cursors, no checkpoint files — each run
reconciles against what Polymarket and Kalshi list *right now* and converges
when re-run):

1. Pull the top active markets from both venues and upsert them
   (`sync_active`): new listings appear, prices/volumes refresh, rows the
   venue reports closed flip inactive.
2. `deactivate_stale`: events not seen for --stale-hours are delisted from
   trading (kept in the corpus; open positions untouched).
3. Settlement sweep: for active-or-recently-active events whose venue row
   now shows a YES/NO resolution, record the outcome and pay out positions
   via app.trading.settle_event.

Play money · paper trading · real market prices — ⓥ credits are virtual;
nothing here moves real money.

Usage:
    python scripts/sync_markets.py
    python scripts/sync_markets.py --polymarket-pages 10 --kalshi-pages 2
    python scripts/sync_markets.py --loop 15        # repeat every 15 minutes
"""

import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
POLYMARKET_PAGE_SIZE = 100
KALSHI_PAGE_SIZE = 1000
PAGE_SLEEP_SECONDS = 0.05
# "Recently active": how long after its last sync a now-inactive event still
# gets settlement probes — covers venues that delist before resolution lands.
RECENTLY_ACTIVE_HOURS = 72
SETTLE_BUDGET = 200


def _utc(value: datetime | None) -> datetime | None:
    """SQLite round-trips drop tzinfo; naive datetimes here mean UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def pull_active(session, polymarket_pages: int, kalshi_pages: int) -> dict:
    """Stage 1: fetch + reconcile both venues. Returns merged counts."""
    from app.ingest.active import (
        fetch_active_kalshi,
        fetch_active_polymarket,
        normalize_active,
        sync_active,
    )

    counts = {"added": 0, "updated": 0, "closed": 0}

    for page in range(polymarket_pages):
        markets = fetch_active_polymarket(page * POLYMARKET_PAGE_SIZE, POLYMARKET_PAGE_SIZE)
        if not markets:
            break
        rows = [row for row in (normalize_active(market) for market in markets) if row is not None]
        for key, value in sync_active(session, rows, "polymarket").items():
            counts[key] += value
        session.commit()
        time.sleep(PAGE_SLEEP_SECONDS)

    cursor = None
    for _ in range(kalshi_pages):
        rows, cursor = fetch_active_kalshi(cursor, KALSHI_PAGE_SIZE)
        for key, value in sync_active(session, rows, "kalshi").items():
            counts[key] += value
        session.commit()
        if cursor is None:
            break
        time.sleep(PAGE_SLEEP_SECONDS)
    return counts


def settlement_sweep(session, fetch_row=None, budget: int = SETTLE_BUDGET) -> int:
    """Stage 3: find venue-resolved events and settle their positions.

    Candidates are unresolved events that are still active with their close
    time passed, or recently active but delisted (venues often drop a market
    from the feed before the resolution reaches the API). Each candidate
    costs one venue request, so the sweep is budgeted. Returns the number of
    events settled this pass."""
    try:
        from app.trading import settle_event
    except ImportError as exc:  # pragma: no cover - exercised via sys.modules poisoning
        raise RuntimeError(
            "app.trading is not available — the settlement sweep needs "
            "app.trading.settle_event to pay out positions. Deploy the "
            "trading module (or run with --no-settle) before syncing."
        ) from exc

    from sqlalchemy import select

    from app.ingest import active as active_module
    from app.models import MarketEvent

    if fetch_row is None:
        fetch_row = active_module.fetch_venue_row
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=RECENTLY_ACTIVE_HOURS)

    candidates = []
    for event in session.scalars(
        select(MarketEvent).where(MarketEvent.outcome.is_(None), MarketEvent.last_synced.is_not(None))
    ):
        last_synced = _utc(event.last_synced)
        close_time = _utc(event.close_time)
        if event.active:
            # Still listed: only probe once the stated close has passed.
            if close_time is not None and close_time <= now:
                candidates.append(event)
        elif last_synced >= recent_cutoff:
            # Recently delisted: the venue may have settled it off-feed.
            candidates.append(event)

    settled = 0
    for event in candidates[:budget]:
        row = fetch_row(event.source, event.source_id)
        outcome = active_module.resolution_of(event.source, row)
        if outcome is None:
            continue
        event.outcome = outcome
        event.active = False
        settle_event(session, event)
        session.commit()  # per-event: a crash mid-sweep never re-pays settled events
        settled += 1
    return settled


def run_pass(session, args) -> dict:
    """One full stateless pass. Returns the printed counts."""
    from app.ingest.active import deactivate_stale

    counts = pull_active(session, args.polymarket_pages, args.kalshi_pages)
    counts["deactivated"] = deactivate_stale(session, "polymarket", args.stale_hours) + deactivate_stale(
        session, "kalshi", args.stale_hours
    )
    session.commit()
    counts["settled"] = settlement_sweep(session) if args.settle else 0
    session.commit()
    print(
        f"sync: added={counts['added']} updated={counts['updated']} closed={counts['closed']} "
        f"deactivated={counts['deactivated']} settled={counts['settled']}",
        flush=True,
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--polymarket-pages", type=int, default=30, help="gamma pages of 100 to pull (top volume)")
    parser.add_argument("--kalshi-pages", type=int, default=3, help="kalshi pages of 1000 to pull")
    parser.add_argument("--stale-hours", type=float, default=24.0, help="deactivate events unseen this long")
    parser.add_argument(
        "--settle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run the settlement sweep (needs app.trading)",
    )
    parser.add_argument("--loop", type=float, default=None, metavar="MINUTES", help="repeat forever, sleeping between")
    parser.add_argument("--db", default=str(BACKEND_DIR / "vanta.db"), help="SQLite database path")
    args = parser.parse_args()

    # Bind the target DB before any app import — app/db.py creates its
    # engine at first import (same bootstrap as the other ingest scripts).
    db_path = Path(args.db).resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.config import get_settings

    get_settings.cache_clear()

    from app import models  # noqa: F401 — register tables on Base before create_all
    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)

    while True:
        try:
            with SessionLocal() as session:
                run_pass(session, args)
        except Exception:
            if args.loop is None:
                raise
            # Daemon mode shrugs off a bad pass (venue outage, rate-limit
            # storm) — statelessness means the next pass reconverges.
            import traceback

            traceback.print_exc()
        if args.loop is None:
            return 0
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    raise SystemExit(main())
