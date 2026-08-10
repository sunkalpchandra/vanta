"""Idempotent migration for v0.5 tables (price_ticks, agent_traders).

create_all() adds the new tables; there are no column alters this round.

    python scripts/migrate_v05.py [--db PATH]
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

    from app import models  # noqa: F401 — register tables on Base
    from app.db import Base, engine

    Base.metadata.create_all(engine)
    print("migration complete: price_ticks, agent_traders ensured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
