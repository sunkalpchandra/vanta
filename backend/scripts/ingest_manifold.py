"""Ingest Manifold Markets — the third venue.

Two independent jobs, either or both per run:

1. Corpus backfill (--limit-events): page GET /v0/markets newest-first by the
   `before` cursor, normalize the binary rows, and upsert them into the
   market_events backtest corpus (idempotent by (source, source_id) — the
   shared Polymarket `upsert_events`, which also refreshes settlement fields
   on rows first seen unresolved). A checkpoint (.ingest_manifold_ckpt.json
   next to the DB) resumes the cursor across runs.

2. Active sync (--active): pull the freshest pages, keep the tradable binary
   markets (`normalize_active`), and reconcile them onto the play-money
   trading surface via the stateless `sync_active`. Stateless — no cursor is
   kept; each run reconciles against Manifold's current listings.

Play money · paper trading · real market prices — ⓥ credits are virtual;
nothing here moves real money.

Usage:
    python scripts/ingest_manifold.py --limit-events 5000
    python scripts/ingest_manifold.py --active --active-pages 5
    python scripts/ingest_manifold.py --limit-events 2000 --active --db /tmp/x.db
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PAGE_SIZE = 1000
COMMIT_EVERY = 2000
PROGRESS_EVERY = 5000
PAGE_SLEEP_SECONDS = 0.1


def load_checkpoint(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except ValueError:
            pass  # corrupt checkpoint: restart from the top — upserts make that safe
    return {}


def save_checkpoint(path: Path, ckpt: dict) -> None:
    path.write_text(json.dumps(ckpt))


def ingest_markets(session, ckpt: dict, ckpt_path: Path, limit_events: int) -> None:
    """Job 1: page Manifold by cursor, normalize, upsert-skip into the corpus."""
    from app.ingest.manifold import fetch_markets, normalize
    from app.ingest.polymarket import upsert_events

    before = ckpt.get("before")
    kept_total = skipped_total = rejected_total = 0
    scanned = since_commit = since_print = 0

    def flush() -> None:
        nonlocal since_commit
        session.commit()  # commit before checkpointing so a crash re-walks, never skips
        ckpt["before"] = before
        save_checkpoint(ckpt_path, ckpt)
        since_commit = 0

    while kept_total < limit_events:
        page = fetch_markets(before=before, limit=PAGE_SIZE)
        if not page:
            before = None  # exhausted: reset so the next run re-walks from newest
            break
        rows = [row for row in (normalize(m) for m in page) if row is not None]
        kept, skipped = upsert_events(session, rows)
        kept_total += kept
        skipped_total += skipped
        rejected_total += len(page) - len(rows)
        scanned += len(page)
        since_commit += len(page)
        since_print += len(page)
        before = page[-1]["id"]  # cursor = last id of the page
        if since_commit >= COMMIT_EVERY:
            flush()
        if since_print >= PROGRESS_EVERY:
            print(
                f"markets: scanned={scanned} kept={kept_total} skipped={skipped_total} rejected={rejected_total}",
                flush=True,
            )
            since_print = 0
        time.sleep(PAGE_SLEEP_SECONDS)
    flush()
    print(f"markets done: scanned={scanned} kept={kept_total} skipped={skipped_total} rejected={rejected_total}")


def sync_active_markets(session, pages: int) -> None:
    """Job 2: reconcile the freshest tradable Manifold markets onto the
    trading surface. Stateless — walks `pages` pages from the newest market
    each run and lets `sync_active` add/update/relist as the venue moves."""
    from app.ingest.active import sync_active
    from app.ingest.manifold import SOURCE, fetch_markets, normalize_active

    counts = {"added": 0, "updated": 0, "closed": 0}
    before = None
    for _ in range(pages):
        page = fetch_markets(before=before, limit=PAGE_SIZE)
        if not page:
            break
        rows = [row for row in (normalize_active(m) for m in page) if row is not None]
        for key, value in sync_active(session, rows, SOURCE).items():
            counts[key] += value
        session.commit()
        before = page[-1]["id"]
        time.sleep(PAGE_SLEEP_SECONDS)
    print(f"active: added={counts['added']} updated={counts['updated']} closed={counts['closed']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit-events", type=int, default=0, help="max new corpus events to ingest (0 = skip)")
    parser.add_argument("--active", action="store_true", help="sync active markets onto the trading surface")
    parser.add_argument("--active-pages", type=int, default=5, help="pages (of 1000) to scan for active markets")
    parser.add_argument("--db", default=str(BACKEND_DIR / "vanta.db"), help="SQLite database path")
    args = parser.parse_args()

    if args.limit_events <= 0 and not args.active:
        parser.error("nothing to do: pass --limit-events N and/or --active")

    # Bind the target DB before any app import — app/db.py creates its engine
    # at first import (same bootstrap as the other ingest scripts).
    db_path = Path(args.db).resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    sys.path.insert(0, str(BACKEND_DIR))

    from app.config import get_settings

    get_settings.cache_clear()

    from app import models  # noqa: F401 — register tables on Base before create_all
    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)

    ckpt_path = db_path.parent / ".ingest_manifold_ckpt.json"
    ckpt = load_checkpoint(ckpt_path)
    with SessionLocal() as session:
        if args.limit_events > 0:
            ingest_markets(session, ckpt, ckpt_path, args.limit_events)
        if args.active:
            sync_active_markets(session, args.active_pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
