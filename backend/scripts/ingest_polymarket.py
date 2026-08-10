"""Ingest closed Polymarket markets into the market_events backtest corpus.

Two stages:
1. Markets — pages gamma /markets by offset until the API's depth cap
   (~2000), then walks /markets/keyset by cursor. Rows upsert by
   (source, source_id) with existing rows skipped, so re-runs are cheap;
   a checkpoint file (.ingest_polymarket_ckpt.json next to the DB) resumes
   pagination across runs.
2. Prices — for resolved events still missing price_7d, fetches the YES
   token's daily CLOB history and fills price_7d/price_30d via price_at
   (which never reads points after T-h). Budgeted by --price-budget.

Usage:
    python scripts/ingest_polymarket.py --limit-events 5000 --price-budget 500
    python scripts/ingest_polymarket.py --no-prices --db /tmp/scratch.db
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PAGE_SIZE = 100
COMMIT_EVERY_MARKETS = 500
COMMIT_EVERY_PRICES = 100
PROGRESS_EVERY = 1000
PRICE_SLEEP_SECONDS = 0.08


def load_checkpoint(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except ValueError:
            pass  # corrupt checkpoint: restart from zero — upserts make that safe
    return {}


def save_checkpoint(path: Path, ckpt: dict) -> None:
    path.write_text(json.dumps(ckpt))


def ingest_markets(session, ckpt: dict, ckpt_path: Path, limit_events: int) -> None:
    """Stage 1: page the gamma API, normalize, upsert-skip into market_events."""
    from app.ingest.polymarket import (
        OffsetCapReached,
        fetch_markets,
        fetch_markets_keyset,
        normalize,
        upsert_events,
    )

    offset = int(ckpt.get("offset") or 0)
    cursor = ckpt.get("cursor")
    keyset = bool(ckpt.get("keyset"))
    kept_total = skipped_total = rejected_total = 0
    since_commit = since_print = 0

    def flush() -> None:
        nonlocal since_commit
        session.commit()  # commit before checkpointing so a crash re-walks, never skips
        ckpt.update(offset=offset, cursor=cursor, keyset=keyset)
        save_checkpoint(ckpt_path, ckpt)
        since_commit = 0

    exhausted = False
    while not exhausted and kept_total < limit_events:
        if not keyset:
            try:
                page = fetch_markets(offset, PAGE_SIZE)
            except OffsetCapReached:
                # Keyset cursors are opaque, so the walk restarts from the
                # front — cheap, because every already-ingested row skips.
                keyset = True
                continue
            if not page:
                exhausted = True
        else:
            page, cursor = fetch_markets_keyset(cursor, PAGE_SIZE)
            exhausted = not page or cursor is None
        rows = [row for row in (normalize(market) for market in page) if row is not None]
        kept, skipped = upsert_events(session, rows)
        kept_total += kept
        skipped_total += skipped
        rejected_total += len(page) - len(rows)
        offset += len(page)
        since_commit += len(page)
        since_print += len(page)
        if since_commit >= COMMIT_EVERY_MARKETS:
            flush()
        if since_print >= PROGRESS_EVERY:
            print(
                f"markets: offset={offset} kept={kept_total} skipped={skipped_total} rejected={rejected_total}",
                flush=True,
            )
            since_print = 0
        time.sleep(0.05)  # be polite between pages
    flush()
    if kept_total:
        # New rows land at the HIGHEST ids — above any partial-pass price
        # watermark. Reset it so the newest-first walk sees them next run.
        ckpt.pop("price_before_id", None)
        save_checkpoint(ckpt_path, ckpt)
    print(f"markets done: offset={offset} kept={kept_total} skipped={skipped_total} rejected={rejected_total}")


def fill_prices(session, ckpt: dict, ckpt_path: Path, budget: int) -> None:
    """Stage 2: fill price_7d/price_30d on resolved events that lack them.

    Walks events by id from the checkpointed watermark so short-lived
    markets with empty history (price_7d stays NULL) aren't refetched every
    run; a completed pass resets the watermark so they retry eventually.
    """
    from sqlalchemy import select

    from app.ingest.polymarket import SOURCE, fetch_price_history, price_at
    from app.models import MarketEvent

    # Walk NEWEST-first: AMM-era rows (low ids, pre-2022) have no CLOB
    # history, so ascending order burns the whole budget discovering empties.
    before_id = int(ckpt.get("price_before_id") or 2**62)
    fetched = filled = 0
    completed_pass = False
    since_commit = 0

    def flush() -> None:
        nonlocal since_commit
        session.commit()
        ckpt["price_before_id"] = before_id
        save_checkpoint(ckpt_path, ckpt)
        since_commit = 0

    budget_hit = False
    while not budget_hit:
        events = session.scalars(
            select(MarketEvent)
            .where(
                MarketEvent.source == SOURCE,
                MarketEvent.outcome.is_not(None),
                MarketEvent.price_7d.is_(None),
                MarketEvent.close_time.is_not(None),
                MarketEvent.id < before_id,
            )
            .order_by(MarketEvent.id.desc())
            .limit(200)
        ).all()
        if not events:
            before_id = 2**62  # full pass complete: retry empties from the top
            if completed_pass:
                break  # second completion this run — corpus fully swept
            completed_pass = True
            continue
        for event in events:
            if fetched >= budget:
                budget_hit = True
                break
            before_id = event.id
            tokens = (event.raw or {}).get("clobTokenIds") or []
            if not tokens:
                continue
            history = fetch_price_history(tokens[0])  # index 0 = YES token
            fetched += 1
            price_7d = price_at(history, event.close_time, 7)
            price_30d = price_at(history, event.close_time, 30)
            if price_7d is not None:
                event.price_7d = price_7d
                filled += 1
            if price_30d is not None:
                event.price_30d = price_30d
            since_commit += 1
            if since_commit >= COMMIT_EVERY_PRICES:
                flush()
                print(f"prices: before_id={before_id} fetched={fetched} filled={filled}", flush=True)
            time.sleep(PRICE_SLEEP_SECONDS)
    flush()
    print(f"prices done: fetched={fetched} filled={filled} budget={budget}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit-events", type=int, default=100000, help="max new events to ingest this run")
    parser.add_argument("--db", default=str(BACKEND_DIR / "vanta.db"), help="SQLite database path")
    parser.add_argument(
        "--prices",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run the price-history stage after ingesting markets",
    )
    parser.add_argument("--price-budget", type=int, default=500, help="max price-history fetches this run")
    args = parser.parse_args()

    # Bind the target DB before any app import — app/db.py creates its
    # engine at first import (same bootstrap as scripts/export_snapshot.py).
    db_path = Path(args.db).resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.config import get_settings

    get_settings.cache_clear()

    from app import models  # noqa: F401 — register tables on Base before create_all
    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)

    ckpt_path = db_path.parent / ".ingest_polymarket_ckpt.json"
    ckpt = load_checkpoint(ckpt_path)
    with SessionLocal() as session:
        ingest_markets(session, ckpt, ckpt_path, args.limit_events)
        if args.prices:
            fill_prices(session, ckpt, ckpt_path, args.price_budget)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
