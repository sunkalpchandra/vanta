"""Market-surface stats + biggest movers for the play-money trading UI.

Read-only and open (no identity). Two endpoints:

- GET /api/market-stats          -> cheap COUNT/SUM aggregates over the corpus
- GET /api/market-stats/movers   -> active markets with the biggest |yes_price|
                                    change over a recent window, from PriceTick

Why the `/api/market-stats` prefix and not `/api/markets/stats`:
`markets.router` owns `GET /api/markets/{event_id}` (a single-segment path
param). A single-segment `/api/markets/stats` matches that route first (Starlette
matches by registration order and never backtracks once a path pattern hits), so
with markets.router registered ahead of us `stats`/`movers` get parsed as an int
`event_id` and 422 before ever reaching this handler — verified in the tests.
Making it work would require guaranteeing this router is included BEFORE
markets.router in the shared main.py, which this slice can't own. `/api/market-stats`
is a distinct literal segment that can never collide, regardless of order — the
safe option the task asked us to pick.

Play money only — virtual ⓥ credits, paper trading at real synced venue prices,
never real money. Deterministic reads: no LLM ever touches these numbers.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent, Position, PriceTick, Trade, utcnow

router = APIRouter(prefix="/api/market-stats", tags=["markets"])

# The venues we surface a per-source breakdown for. Events from other sources
# (ingest experiments, test fixtures) still count toward n_active but are not
# broken out here.
KNOWN_SOURCES = ("polymarket", "kalshi", "manifold")


class BySource(BaseModel):
    polymarket: int = 0
    kalshi: int = 0
    manifold: int = 0


class MarketStatsOut(BaseModel):
    n_active: int
    n_settled: int
    # Active-surface breakdown by venue (sums to n_active only when every active
    # event is from a known venue — test/ingest sources are excluded here).
    by_source: BySource
    total_volume_usd: float  # summed over the whole corpus, rounded to cents
    n_traders: int  # distinct users who have placed at least one trade
    n_open_positions: int  # unsettled positions still holding shares
    n_trades: int


class MarketMoverOut(BaseModel):
    event_id: int
    question: str
    source: str
    yes_price: float  # current synced YES price
    prev_price: float  # YES price at the earliest tick inside the window
    change: float  # signed: current - prev (positive = moved up)
    volume_usd: float


@router.get("", response_model=MarketStatsOut)
def market_stats(db: Session = Depends(get_db)):
    """Corpus-wide surface counts for the markets stat bar. All cheap
    COUNT/SUM aggregates — no per-row Python."""
    n_active = db.scalar(select(func.count()).select_from(MarketEvent).where(MarketEvent.active.is_(True))) or 0
    n_settled = (
        db.scalar(select(func.count()).select_from(MarketEvent).where(MarketEvent.outcome.is_not(None))) or 0
    )

    source_counts = dict(
        db.execute(
            select(MarketEvent.source, func.count())
            .where(MarketEvent.active.is_(True))
            .group_by(MarketEvent.source)
        ).all()
    )
    by_source = BySource(**{source: int(source_counts.get(source, 0)) for source in KNOWN_SOURCES})

    total_volume_usd = db.scalar(select(func.coalesce(func.sum(MarketEvent.volume_usd), 0.0))) or 0.0

    # "Traders" = participants who have actually traded (matches the leaderboard,
    # which excludes registered-but-never-traded users), not the raw user count.
    n_traders = db.scalar(select(func.count(func.distinct(Trade.user_id)))) or 0
    n_open_positions = (
        db.scalar(
            select(func.count())
            .select_from(Position)
            .where(Position.settled.is_(False), Position.shares > 0)
        )
        or 0
    )
    n_trades = db.scalar(select(func.count()).select_from(Trade)) or 0

    return MarketStatsOut(
        n_active=int(n_active),
        n_settled=int(n_settled),
        by_source=by_source,
        total_volume_usd=round(float(total_volume_usd), 2),
        n_traders=int(n_traders),
        n_open_positions=int(n_open_positions),
        n_trades=int(n_trades),
    )


@router.get("/movers", response_model=list[MarketMoverOut])
def market_movers(
    window_hours: float = Query(24, gt=0, le=720),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Active markets ranked by the size of their YES-price move over the last
    `window_hours`, biggest absolute change first. The reference price is the
    earliest PriceTick recorded inside the window; the current price is the
    event's synced `yes_price`. Only markets with at least one tick in the
    window are eligible (no tick -> no measurable move -> excluded)."""
    window_start = utcnow() - timedelta(hours=window_hours)

    # Earliest in-window tick timestamp per event...
    earliest = (
        select(
            PriceTick.event_id.label("event_id"),
            func.min(PriceTick.timestamp).label("min_ts"),
        )
        .where(PriceTick.timestamp >= window_start)
        .group_by(PriceTick.event_id)
        .subquery()
    )
    # ...joined back to read the price AT that earliest timestamp, and to the
    # event for its live price/metadata (active + priced markets only).
    rows = db.execute(
        select(
            MarketEvent.id,
            MarketEvent.question,
            MarketEvent.source,
            MarketEvent.yes_price,
            MarketEvent.volume_usd,
            PriceTick.yes_price,
        )
        .join(earliest, earliest.c.event_id == MarketEvent.id)
        .join(
            PriceTick,
            (PriceTick.event_id == earliest.c.event_id) & (PriceTick.timestamp == earliest.c.min_ts),
        )
        .where(MarketEvent.active.is_(True), MarketEvent.yes_price.is_not(None))
    ).all()

    seen: set[int] = set()
    movers: list[MarketMoverOut] = []
    for event_id, question, source, current, volume, prev in rows:
        if event_id in seen:  # defensive: two ticks sharing the exact min timestamp
            continue
        seen.add(event_id)
        movers.append(
            MarketMoverOut(
                event_id=event_id,
                question=question,
                source=source,
                yes_price=round(current, 6),
                prev_price=round(prev, 6),
                change=round(current - prev, 6),
                volume_usd=volume,
            )
        )
    # Biggest absolute move first; stable sort keeps input order on ties.
    movers.sort(key=lambda m: abs(m.change), reverse=True)
    return movers[:limit]
