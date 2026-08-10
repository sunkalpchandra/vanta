"""Backfill price-history ticks for active Polymarket markets from the venue's
own CLOB daily price series.

The live sync records one tick per event per hour going forward, but a fresh
deployment has no history to chart. This seeds real, multi-point series from
Polymarket's public price history so the market detail charts are meaningful
from day one. Idempotent: skips events that already have ticks.

    python scripts/backfill_ticks.py --max-events 150
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-events", type=int, default=150, help="active PM events to backfill (volume desc)")
    parser.add_argument("--db", default=str(BACKEND_DIR / "vanta.db"))
    args = parser.parse_args()

    import os

    os.environ["DATABASE_URL"] = f"sqlite:///{Path(args.db).resolve()}"

    from app.db import Base, SessionLocal, engine
    from app.ingest.polymarket import fetch_price_history
    from app.models import MarketEvent, PriceTick

    Base.metadata.create_all(bind=engine)
    written = 0
    with SessionLocal() as db:
        events = (
            db.query(MarketEvent)
            .filter(
                MarketEvent.source == "polymarket",
                MarketEvent.active.is_(True),
                MarketEvent.yes_price.is_not(None),
            )
            .order_by(MarketEvent.volume_usd.desc())
            .limit(args.max_events)
            .all()
        )
        for i, event in enumerate(events, 1):
            if db.query(PriceTick).filter(PriceTick.event_id == event.id).first():
                continue  # already has history
            tokens = (event.raw or {}).get("clobTokenIds") or []
            if not tokens:
                continue
            history = fetch_price_history(tokens[0])  # index 0 = YES token
            for point in history:
                ts = datetime.fromtimestamp(int(point["t"]), tz=UTC)
                db.add(PriceTick(event_id=event.id, yes_price=float(point["p"]), timestamp=ts))
                written += 1
            if i % 20 == 0:
                db.commit()
                print(f"backfill: {i}/{len(events)} events, {written} ticks", flush=True)
            time.sleep(0.05)
        db.commit()
    print(f"backfill done: {written} ticks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
