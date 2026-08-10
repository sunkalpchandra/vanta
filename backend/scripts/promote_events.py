"""Promote real ACTIVE Polymarket markets into the live product feed.

Fetches currently-open markets (highest volume first), normalizes them with
the same ingest machinery as the backtest corpus, and creates real Questions
with the venue's live price as market_probability — then runs the full agent
pipeline on each. The feed stops being synthetic the moment this runs.

    python scripts/promote_events.py --count 25
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.ingest.polymarket import GAMMA_MARKETS_URL, _get_json, normalize_category  # noqa: E402
from app.models import Question  # noqa: E402
from app.service import create_question, run_and_store_forecast  # noqa: E402


def fetch_active(limit: int) -> list[dict]:
    return _get_json(
        GAMMA_MARKETS_URL,
        params={
            "closed": "false",
            "active": "true",
            "limit": min(limit * 3, 100),  # headroom: some rows won't normalize
            "order": "volumeNum",
            "ascending": "false",
            "include_tag": "true",
        },
    )


def promotable(market: dict) -> dict | None:
    """Active-market variant of the ingest normalizer: binary, has a live
    mid-price strictly inside (0,1), and a real question text."""
    import json as _json

    try:
        outcomes = market.get("outcomes")
        if isinstance(outcomes, str):
            outcomes = _json.loads(outcomes)
    except (ValueError, TypeError):
        return None  # malformed row must not kill the whole promotion run
    if outcomes != ["Yes", "No"]:
        return None
    question = (market.get("question") or "").strip()
    if len(question) < 10:
        return None
    try:
        prices = market.get("outcomePrices")
        if isinstance(prices, str):
            prices = _json.loads(prices)
        yes_price = float(prices[0])
    except (TypeError, ValueError, IndexError):
        return None
    if not (0.01 <= yes_price <= 0.99):
        return None  # near-settled or dead markets make degenerate questions
    return {
        "question": question[:500],
        "category": normalize_category(
            market.get("category"),
            [t.get("label", "") for t in market.get("tags") or [] if isinstance(t, dict)],
        ),
        "market_probability": yes_price,
        "volume": float(market.get("volumeNum") or market.get("volume") or 0.0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=25)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    created = 0
    with SessionLocal() as db:
        existing = {q.question for q in db.query(Question).all()}
        for market in fetch_active(args.count):
            if created >= args.count:
                break
            values = promotable(market)
            if values is None or values["question"] in existing:
                continue
            if values["category"] == "other":
                continue  # don't mislabel — the product's category set is closed
            category = values["category"]
            volume = values["volume"]
            liquidity = "high" if volume >= 1_000_000 else "medium" if volume >= 100_000 else "low"
            question = create_question(
                db,
                text=values["question"],
                category=category,
                horizon_days=90,
                market_probability=values["market_probability"],
                market_volume_usd=volume,
                market_liquidity=liquidity,
            )
            run_and_store_forecast(db, question)
            existing.add(values["question"])
            created += 1
            print(f"promoted #{question.id} [{category}] {values['question'][:70]}")
    print(f"done: {created} active markets promoted into the feed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
