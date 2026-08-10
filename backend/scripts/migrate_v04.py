"""One-shot SQLite migration for the v0.4 trading columns/tables.

create_all() adds NEW tables but never alters existing ones — the corpus DB
predates the trading columns, so they're added here idempotently.

    python scripts/migrate_v04.py [--db PATH]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    if args.db:
        import os

        os.environ["DATABASE_URL"] = f"sqlite:///{args.db}"

    from sqlalchemy import text

    from app.db import Base, engine

    Base.metadata.create_all(engine)  # new tables: positions, trades
    statements = [
        "ALTER TABLE users ADD COLUMN balance FLOAT DEFAULT 10000.0",
        "ALTER TABLE market_events ADD COLUMN active BOOLEAN DEFAULT 0",
        "ALTER TABLE market_events ADD COLUMN yes_price FLOAT",
        "ALTER TABLE market_events ADD COLUMN last_synced DATETIME",
        "CREATE INDEX IF NOT EXISTS ix_market_events_active ON market_events (active)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
                print(f"applied: {statement}")
            except Exception as exc:  # column exists — idempotent re-run
                if "duplicate column" in str(exc).lower():
                    print(f"skipped (exists): {statement}")
                else:
                    raise
    print("migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
