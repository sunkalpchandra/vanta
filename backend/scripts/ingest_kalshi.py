"""Ingest settled Kalshi markets into the market_events backtest corpus.

Two passes: (1) page GET /markets with the cursor checkpointed to
.ingest_kalshi_ckpt.json so interrupted runs resume where they stopped, and
(2) optionally fill price_7d/price_30d from the candlesticks endpoint for
rows that still lack them (budgeted — it is one API call per market).

Recent settled pages are dominated by multivariate combo junk (KXMVE...);
the normalizer drops those, and --max-close-days lets a run start paging
from before the junk era instead of wading through it.

Usage:
    python scripts/ingest_kalshi.py --limit-events 5000 --no-prices
    python scripts/ingest_kalshi.py --limit-events 0 --price-budget 300
    python scripts/ingest_kalshi.py --fresh --max-close-days 30
"""

import argparse
import json
import sys
import time
from datetime import UTC, timedelta
from pathlib import Path

CKPT_FILE = Path(".ingest_kalshi_ckpt.json")
COMMIT_EVERY = 500
CANDLE_WINDOW_DAYS = 40  # covers the 30d snapshot with slack for quiet days
REQUEST_PAUSE_S = 0.15  # stay well inside Kalshi's public rate limit


def load_ckpt() -> dict:
    if CKPT_FILE.exists():
        return json.loads(CKPT_FILE.read_text())
    return {}


def save_ckpt(ckpt: dict) -> None:
    CKPT_FILE.write_text(json.dumps(ckpt, indent=1))


def ingest_markets(db, client, args) -> None:
    from app.ingest.kalshi import fetch_markets, normalize, upsert_event

    ckpt = {} if args.fresh else load_ckpt()
    cursor = ckpt.get("cursor")
    scanned = ckpt.get("scanned", 0)
    kept = ckpt.get("kept", 0)
    max_close_ts = None
    if args.max_close_days:
        max_close_ts = int(time.time()) - args.max_close_days * 86400
    upserted = 0
    while upserted < args.limit_events:
        markets, cursor = fetch_markets(
            cursor, limit=1000, status=args.status, max_close_ts=max_close_ts, client=client
        )
        if not markets:
            print("pagination exhausted")
            cursor = None
        for market in markets:
            scanned += 1
            values = normalize(market)
            if values is None:
                continue
            upsert_event(db, values)
            kept += 1
            upserted += 1
            if upserted % COMMIT_EVERY == 0:
                db.commit()
            if upserted >= args.limit_events:
                break
        db.commit()
        save_ckpt({"cursor": cursor, "scanned": scanned, "kept": kept})
        print(f"scanned={scanned} kept={kept} (+{upserted} this run) cursor={'yes' if cursor else 'exhausted'}")
        if cursor is None:
            break
        time.sleep(REQUEST_PAUSE_S)


def fill_prices(db, client, args) -> None:
    from app.ingest.kalshi import SOURCE, fetch_candles, price_at
    from app.models import MarketEvent

    rows = (
        db.query(MarketEvent)
        .filter(
            MarketEvent.source == SOURCE,
            MarketEvent.outcome.isnot(None),
            MarketEvent.close_time.isnot(None),
            MarketEvent.price_7d.is_(None),
        )
        .order_by(MarketEvent.volume_usd.desc())
        .limit(args.price_budget)
        .all()
    )
    print(f"price pass: {len(rows)} rows (budget {args.price_budget})")
    filled = misses = 0
    for i, row in enumerate(rows, 1):
        close = row.close_time
        if close.tzinfo is None:  # SQLite round-trips drop tzinfo
            close = close.replace(tzinfo=UTC)
        series = str(row.raw.get("event_ticker") or row.source_id).split("-")[0]
        start_ts = int((close - timedelta(days=CANDLE_WINDOW_DAYS)).timestamp())
        closes = fetch_candles(series, row.source_id, start_ts, int(close.timestamp()), client=client)
        if closes:
            row.price_7d = price_at(closes, close, 7)
            row.price_30d = price_at(closes, close, 30)
            filled += 1
        else:
            misses += 1
        if i % 50 == 0:
            db.commit()
            print(f"  priced {i}/{len(rows)} (filled={filled} misses={misses})")
        time.sleep(REQUEST_PAUSE_S)
    db.commit()
    print(f"price pass done: filled={filled} misses={misses}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit-events", type=int, default=5000, help="max events to upsert this run (0 = skip)")
    parser.add_argument(
        "--prices", action=argparse.BooleanOptionalAction, default=True, help="fill price_7d/price_30d from candles"
    )
    parser.add_argument("--price-budget", type=int, default=500, help="max candle fetches per run (1 per market)")
    parser.add_argument("--status", default="settled", help="Kalshi market status filter")
    parser.add_argument("--max-close-days", type=int, default=None, help="only markets closed at least N days ago")
    parser.add_argument("--fresh", action="store_true", help="ignore the cursor checkpoint and restart pagination")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    import httpx

    from app.db import Base, SessionLocal, engine
    from app.ingest.kalshi import SOURCE
    from app.models import MarketEvent

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        with httpx.Client(timeout=30) as client:
            if args.limit_events > 0:
                ingest_markets(db, client, args)
            if args.prices and args.price_budget > 0:
                fill_prices(db, client, args)
        total = db.query(MarketEvent).filter(MarketEvent.source == SOURCE).count()
        priced = (
            db.query(MarketEvent)
            .filter(MarketEvent.source == SOURCE, MarketEvent.price_7d.isnot(None))
            .count()
        )
        print(f"kalshi corpus: {total} events, {priced} with price_7d")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
