"""Per-trader market watchlist + 24h move alerts.

The watchlist is server-truth (unlike the localStorage-backed reader star): a
`MarketWatch` row is unique per (user, event), and the trader identity is the
same `X-API-Key` used for trading — the key returned once by `POST /api/users`.
Reuses `markets._require_trader` so the 401 semantics never drift from the
money surface. Read-only signal: nothing here moves a balance.

The list annotates each watched market with a trailing-24h price delta and a
`moved` flag — |Δ| ≥ 0.05 against the earliest `PriceTick` inside the window
(the same window/threshold shape as the alerts feed). Deterministic code only.

play money · paper trading · real market prices — never real money.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent, MarketWatch, PriceTick, utcnow
from .markets import _require_trader

# A watched market is "moved" when its price shifted at least this far (in
# probability, i.e. 5 points) over the trailing 24h. Compared against the
# rounded delta so the flag always agrees with the number the UI shows.
MOVE_THRESHOLD = 0.05

router = APIRouter(prefix="/api/watch", tags=["markets"])


class WatchItem(BaseModel):
    event_id: int
    question: str
    yes_price: float | None
    delta_24h: float | None  # current price − earliest in-window tick; null if unknowable
    moved: bool


class WatchAck(BaseModel):
    event_id: int
    watched: bool
    created: bool  # True only when this call inserted the row (201 vs 200)


@router.post("/{event_id}", response_model=WatchAck, status_code=201)
def add_watch(
    event_id: int,
    response: Response,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Watch a market. Idempotent: 201 when newly added, 200 when already
    watched; 404 for an unknown event. The unique (user, event) index is the
    concurrency backstop — a racing duplicate insert collapses to 200."""
    user = _require_trader(db, x_api_key)
    if db.get(MarketEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="market not found")
    existing = db.scalar(
        select(MarketWatch).where(MarketWatch.user_id == user.id, MarketWatch.event_id == event_id)
    )
    if existing is not None:
        response.status_code = 200
        return WatchAck(event_id=event_id, watched=True, created=False)
    db.add(MarketWatch(user_id=user.id, event_id=event_id))
    try:
        db.commit()
    except IntegrityError:  # lost the race to another add — already watched
        db.rollback()
        response.status_code = 200
        return WatchAck(event_id=event_id, watched=True, created=False)
    return WatchAck(event_id=event_id, watched=True, created=True)


@router.delete("/{event_id}", status_code=204)
def remove_watch(
    event_id: int,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Stop watching a market. 204 on removal; 404 if it wasn't watched."""
    user = _require_trader(db, x_api_key)
    watch = db.scalar(
        select(MarketWatch).where(MarketWatch.user_id == user.id, MarketWatch.event_id == event_id)
    )
    if watch is None:
        raise HTTPException(status_code=404, detail="not watching this market")
    db.delete(watch)
    db.commit()


@router.get("", response_model=list[WatchItem])
def list_watches(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The caller's watched markets with the current price and a computed 24h
    move. `delta_24h`/`moved` are null/false when the market has no synced
    price or no PriceTick inside the trailing-24h window."""
    user = _require_trader(db, x_api_key)
    events = db.scalars(
        select(MarketEvent)
        .join(MarketWatch, MarketWatch.event_id == MarketEvent.id)
        .where(MarketWatch.user_id == user.id)
        .order_by(MarketWatch.created_at.asc(), MarketEvent.id.asc())
    ).all()
    since = utcnow() - timedelta(hours=24)
    # Earliest in-window price per watched event in ONE grouped query + join —
    # not a per-event lookup in the loop (the movers endpoint's pattern).
    event_ids = [e.id for e in events]
    earliest_price: dict[int, float] = {}
    if event_ids:
        earliest = (
            select(PriceTick.event_id.label("event_id"), func.min(PriceTick.timestamp).label("min_ts"))
            .where(PriceTick.timestamp >= since, PriceTick.event_id.in_(event_ids))
            .group_by(PriceTick.event_id)
            .subquery()
        )
        for eid, price in db.execute(
            select(PriceTick.event_id, PriceTick.yes_price).join(
                earliest,
                (PriceTick.event_id == earliest.c.event_id) & (PriceTick.timestamp == earliest.c.min_ts),
            )
        ).all():
            earliest_price.setdefault(eid, price)
    items: list[WatchItem] = []
    for event in events:
        delta: float | None = None
        moved = False
        base = earliest_price.get(event.id)
        if event.yes_price is not None and base is not None:
            delta = round(event.yes_price - base, 6)
            moved = abs(delta) >= MOVE_THRESHOLD
        items.append(
            WatchItem(
                event_id=event.id,
                question=event.question,
                yes_price=event.yes_price,
                delta_24h=delta,
                moved=moved,
            )
        )
    return items
