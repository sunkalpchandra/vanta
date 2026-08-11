"""Global market search — substring match over the real-event corpus.

Read-only surface of the play-money market (virtual ⓥ credits at real synced
venue prices, never real money). Mirrors app/routers/search.py's ilike +
envelope pattern, scoped to MarketEvent instead of Question/Prediction.

Lives under its own /api/market-search prefix rather than /api/markets/search:
the markets router registers `/api/markets/{event_id}` (an int path) ahead of
us, so a `/search` segment there would 422 as a non-int event id — the same
collision the market-stats router sidesteps.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent

router = APIRouter(prefix="/api/market-search", tags=["markets"])


@router.get("")
def market_search(
    q: str = Query(min_length=2, max_length=100),
    status: Literal["active", "settled", "all"] = "active",
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Substring search over real-venue market questions (question ILIKE %q%).

    Active (tradeable) markets rank first, then by descending venue volume, with
    the row id breaking ties — deterministic, so the same query always returns
    the same order. `status` scopes the corpus: active (tradeable now), settled
    (resolved, read-only), or all.
    """
    filters = [MarketEvent.question.ilike(f"%{q}%")]
    if status == "active":
        filters.append(MarketEvent.active.is_(True))
    elif status == "settled":
        filters.append(MarketEvent.outcome.is_not(None))

    stmt = (
        select(MarketEvent)
        .where(*filters)
        .order_by(MarketEvent.active.desc(), MarketEvent.volume_usd.desc(), MarketEvent.id)
        .limit(limit)
    )
    events = db.scalars(stmt).all()
    return {
        "query": q,
        "items": [
            {
                "event_id": e.id,
                "question": e.question,
                "category": e.category,
                "source": e.source,
                "yes_price": e.yes_price,
                "outcome": e.outcome,
                "active": e.active,
            }
            for e in events
        ],
    }
