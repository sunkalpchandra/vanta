"""Settled-markets resolution archive — the read-only settlement history of the
play-money market: which real-venue events resolved, what they settled to, and
whether the market's own final price called the outcome.

Distinct from the settled tab of markets.py (which is the trading surface):
this view exposes `final_price` — the market's YES price at settlement — so a
reader can see whether the market's own last price agreed with the realized
`outcome` (1 YES / 0 NO). vanta doesn't grade itself here; the market grades
itself against reality.

Play money · paper trading · real market prices — never real money.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent
from ..schemas import UTCDateTime

router = APIRouter(prefix="/api/market-archive", tags=["markets"])


class ArchiveItem(BaseModel):
    event_id: int
    question: str
    category: str
    source: str
    outcome: int | None  # 1 YES, 0 NO — non-null for every archived (resolved) row
    final_price: float | None  # market's YES price at settlement, in (0,1)
    close_time: UTCDateTime | None
    volume_usd: float


class ArchiveList(BaseModel):
    total: int
    items: list[ArchiveItem]


@router.get("", response_model=ArchiveList)
def list_archive(
    category: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Recently RESOLVED real-venue markets (outcome not null), newest
    close_time first. Cheap COUNT + one page — the corpus is large, so never
    materialize the whole archive."""
    filters = [MarketEvent.outcome.is_not(None)]
    if category:
        filters.append(MarketEvent.category == category)

    total = db.scalar(select(func.count()).select_from(MarketEvent).where(*filters)) or 0
    stmt = (
        select(MarketEvent)
        .where(*filters)
        # Newest close first; rows without a close time sink to the end. id is a
        # stable, deterministic tiebreak within an equal close_time.
        .order_by(
            MarketEvent.close_time.is_(None),
            MarketEvent.close_time.desc(),
            MarketEvent.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    events = db.scalars(stmt).all()
    items = [
        ArchiveItem(
            event_id=e.id,
            question=e.question,
            category=e.category,
            source=e.source,
            outcome=e.outcome,
            final_price=e.final_price,
            close_time=e.close_time,
            volume_usd=e.volume_usd,
        )
        for e in events
    ]
    return ArchiveList(total=total, items=items)
