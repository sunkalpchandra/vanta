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
MANIFOLD_PAGE_SIZE = 500
PAGE_SLEEP_SECONDS = 0.05
# How long after its last sync a now-delisted event is still probed for a
# resolution the venue dropped before it reached the API.
RECENTLY_ACTIVE_HOURS = 72
# Per-pass cap on venue resolution probes (one request each). The position-
# driven settle_resolved backstop pays out anything the probes miss, so this
# only bounds discovery latency, never whether winners get paid.
SETTLE_BUDGET = 200


def _utc(value: datetime | None) -> datetime | None:
    """SQLite round-trips drop tzinfo; naive datetimes here mean UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def pull_active(session, polymarket_pages: int, kalshi_pages: int, manifold_pages: int = 3) -> dict:
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

    # Manifold as a first-class live venue.
    from app.ingest.manifold import fetch_markets as fetch_manifold
    from app.ingest.manifold import normalize_active as manifold_normalize

    before = None
    for _ in range(manifold_pages):
        markets = fetch_manifold(before, MANIFOLD_PAGE_SIZE)
        if not markets:
            break
        rows = [row for row in (manifold_normalize(m) for m in markets) if row is not None]
        for key, value in sync_active(session, rows, "manifold").items():
            counts[key] += value
        session.commit()
        before = markets[-1].get("id")
        time.sleep(PAGE_SLEEP_SECONDS)
    return counts


def settlement_sweep(session, fetch_row=None, budget: int = SETTLE_BUDGET) -> int:
    """Stage 3: discover venue resolutions and pay out positions.

    Probes unresolved past-close events (newest close first, budgeted — one
    venue request each) to record outcomes, then runs settle_resolved as a
    position-driven backstop that pays out EVERY resolved event with unsettled
    positions — including those closed by sync_active and those a prior budget
    couldn't reach. Returns the number of events newly resolved by probing."""
    try:
        from app.trading import settle_event, settle_resolved
    except ImportError as exc:  # pragma: no cover - exercised via sys.modules poisoning
        raise RuntimeError(
            "app.trading is not available — the settlement sweep needs "
            "app.trading to pay out positions. Deploy the trading module "
            "(or run with --no-settle) before syncing."
        ) from exc

    from sqlalchemy import select

    from app.ingest import active as active_module
    from app.models import MarketEvent

    if fetch_row is None:
        fetch_row = active_module.fetch_venue_row
    now = datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=RECENTLY_ACTIVE_HOURS)

    # Discovery candidates (one venue request each, budgeted): unresolved
    # events that are either past their stated close, or recently delisted
    # (venues often drop a market before the resolution reaches the API).
    # Ordered newest-close-first so the budget favors the freshest closes;
    # anything not reached this pass is retried next pass — and payout never
    # waits on discovery thanks to the settle_resolved backstop below.
    candidates = []
    for event in session.scalars(
        select(MarketEvent).where(MarketEvent.outcome.is_(None), MarketEvent.last_synced.is_not(None))
    ):
        close_time = _utc(event.close_time)
        if event.active:
            if close_time is not None and close_time <= now:
                candidates.append(event)
        elif _utc(event.last_synced) >= recent_cutoff:
            candidates.append(event)
    candidates.sort(key=lambda e: _utc(e.close_time) or now, reverse=True)

    resolved = 0
    for event in candidates[:budget]:
        row = fetch_row(event.source, event.source_id)
        outcome = active_module.resolution_of(event.source, row)
        if outcome is None:
            continue
        event.outcome = outcome
        event.active = False
        settle_event(session, event)
        session.commit()  # per-event: a crash mid-sweep never re-pays settled events
        resolved += 1

    # Backstop: pay out EVERY resolved event that still has unsettled positions
    # — including those the sweep's budget couldn't reach and those sync_active
    # closed by recording an outcome without settling. Position-driven, so no
    # payout is ever orphaned by a time window or a budget cap.
    settle_resolved(session)
    session.commit()
    return resolved


def run_pass(session, args) -> dict:
    """One full stateless pass. Returns the printed counts."""
    from app.ingest.active import deactivate_stale

    counts = pull_active(session, args.polymarket_pages, args.kalshi_pages, args.manifold_pages)
    from app.pricehistory import record_ticks_for_active

    counts["ticks"] = record_ticks_for_active(session)
    session.commit()
    counts["deactivated"] = (
        deactivate_stale(session, "polymarket", args.stale_hours)
        + deactivate_stale(session, "kalshi", args.stale_hours)
        + deactivate_stale(session, "manifold", args.stale_hours)
    )
    session.commit()
    counts["settled"] = settlement_sweep(session) if args.settle else 0
    session.commit()
    print(
        f"sync: added={counts['added']} updated={counts['updated']} closed={counts['closed']} "
        f"ticks={counts['ticks']} deactivated={counts['deactivated']} settled={counts['settled']}",
        flush=True,
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--polymarket-pages", type=int, default=30, help="gamma pages of 100 to pull (top volume)")
    parser.add_argument("--kalshi-pages", type=int, default=3, help="kalshi pages of 1000 to pull")
    parser.add_argument("--manifold-pages", type=int, default=3, help="manifold pages of 500 to pull")
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
