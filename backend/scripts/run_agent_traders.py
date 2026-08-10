"""Run vanta's autonomous play-money agent-traders over the live market surface.

Ensures the three strategy bots exist, then runs every strategy once against the
current tradeable markets: the forecasting pipeline runs once per market and each
bot bets (or passes) through the same play-money engine humans use.

Play money · paper trading · real market prices — ⓥ credits are virtual; nothing
here moves real money. Deterministic given the DB — no LLM touches a trade.

Usage:
    python scripts/run_agent_traders.py
    python scripts/run_agent_traders.py --max-markets 50
    python scripts/run_agent_traders.py --loop 30        # repeat every 30 minutes
"""

import argparse
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_pass(session, max_markets: int) -> dict:
    """One full pass: ensure the bots, then trade once. Returns the counts."""
    from app.agent_traders import ensure_agents, run_agents_once

    ensure_agents(session)
    result = run_agents_once(session, max_markets=max_markets)
    print(
        f"agents: evaluated={result['evaluated']} trades={len(result['trades'])}",
        flush=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-markets", type=int, default=200, help="cap markets scanned (top volume first)")
    parser.add_argument("--loop", type=float, default=None, metavar="MINUTES", help="repeat forever, sleeping between")
    parser.add_argument("--db", default=str(BACKEND_DIR / "vanta.db"), help="SQLite database path")
    args = parser.parse_args()

    # Bind the target DB before any app import — app/db.py creates its engine at
    # first import (same bootstrap as the other ingest scripts).
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
                run_pass(session, args.max_markets)
        except Exception:
            if args.loop is None:
                raise
            # Daemon mode shrugs off a bad pass; the next pass reconverges.
            import traceback

            traceback.print_exc()
        if args.loop is None:
            return 0
        time.sleep(args.loop * 60)


if __name__ == "__main__":
    raise SystemExit(main())
