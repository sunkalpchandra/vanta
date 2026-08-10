"""On-demand forecast + agent-debate read API for one live market event.

Merges onto the shared ``/api/markets`` prefix (same ``markets`` tag) alongside
the trading and price-history routers. The route path carries a distinct
``/forecast`` suffix, so it never shadows the single-segment
``GET /api/markets/{event_id}`` or the sibling ``/{event_id}/history``: an
``{event_id}`` path param matches exactly one segment, so
``/api/markets/5/forecast`` resolves to its own handler regardless of
registration order. Test coverage asserts all three resolve.

Reads are open (no operator gate), like the other market read endpoints —
nothing here touches a balance.

play money · paper trading · real market prices — never real money.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..market_forecast import forecast_market
from ..models import MarketEvent

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/{event_id}/forecast")
def market_forecast(event_id: int, db: Session = Depends(get_db)):
    """vanta's deterministic forecast for one market event, with the agent
    debate behind it and its edge versus the venue price. 404 if the event is
    unknown; 409 if it carries no synced price to forecast against."""
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="market not found")
    if event.yes_price is None:
        raise HTTPException(status_code=409, detail="no synced price to forecast against")
    return forecast_market(db, event)
