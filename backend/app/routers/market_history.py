"""Market price-history read API — the series behind a market's price chart.

Merges with the play-money markets router at the app level (same
`/api/markets` prefix, same `markets` tag). The route path carries a distinct
`/history` suffix so it never shadows the existing single-segment
`GET /api/markets/{event_id}` (a `{event_id}` path param matches one path
segment, so `/api/markets/5/history` and `/api/markets/5` resolve to different
routes regardless of registration order). Test coverage asserts both resolve.

play money · paper trading · real market prices — never real money.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent
from ..pricehistory import series
from ..schemas import UTCDateTime

router = APIRouter(prefix="/api/markets", tags=["markets"])


class HistoryPoint(BaseModel):
    timestamp: UTCDateTime
    yes_price: float


class MarketHistoryOut(BaseModel):
    event_id: int
    points: list[HistoryPoint]


@router.get("/{event_id}/history", response_model=MarketHistoryOut)
def market_history(
    event_id: int,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Recorded venue-price history for one market event, oldest-first. 404 if
    the event is unknown; an event with no captured ticks yet returns empty
    points (not an error)."""
    if db.get(MarketEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="market not found")
    points = series(db, event_id, limit=limit)
    return MarketHistoryOut(event_id=event_id, points=[HistoryPoint(**point) for point in points])
