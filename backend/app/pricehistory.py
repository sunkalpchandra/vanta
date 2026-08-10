"""Market price-history capture — the series behind each market's price chart.

Deterministic bookkeeping only: this module reads the already-synced venue
`yes_price` off a MarketEvent and appends observations to `price_ticks`. It
never computes or influences a price (same LLM-free boundary as trading).

Growth is bounded by design: at most one tick per event per hour, and never a
duplicate of the last recorded price. The sync engine calls
`record_ticks_for_active` once per pass; a run that adds no new information
writes nothing.

Datetimes are tz-aware UTC (`models.utcnow`); SQLite round-trips drop tzinfo,
so the dedupe comparison re-stamps a naive stored timestamp as UTC before
measuring its age.
"""

from __future__ import annotations

from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MarketEvent, PriceTick, utcnow

# Minimum spacing between two recorded ticks for the same event. One tick per
# hour keeps ~3 weeks of history under the 500-point series cap.
MIN_TICK_INTERVAL = timedelta(hours=1)

# Prices are probabilities in [0, 1]; treat two within this as identical so
# float round-trips don't defeat the same-price dedupe.
PRICE_EPSILON = 1e-9


def record_tick(db: Session, event: MarketEvent) -> PriceTick | None:
    """Append a PriceTick for `event` at its current synced `yes_price`.

    Deduped to bound growth: skips (returns None) when the latest existing tick
    for this event is less than an hour old OR already carries the same price.
    Also skips when the event has no synced price yet. On write, commits and
    returns the new tick.
    """
    if event.yes_price is None:
        return None

    latest = db.scalar(
        select(PriceTick)
        .where(PriceTick.event_id == event.id)
        .order_by(PriceTick.timestamp.desc(), PriceTick.id.desc())
        .limit(1)
    )
    if latest is not None:
        latest_ts = latest.timestamp if latest.timestamp.tzinfo else latest.timestamp.replace(tzinfo=UTC)
        if utcnow() - latest_ts < MIN_TICK_INTERVAL:
            return None
        if abs(latest.yes_price - event.yes_price) < PRICE_EPSILON:
            return None

    tick = PriceTick(event_id=event.id, yes_price=event.yes_price)
    db.add(tick)
    db.commit()
    db.refresh(tick)
    return tick


def record_ticks_for_active(db: Session) -> int:
    """Record a tick for every active event that has a synced price. Returns the
    number of ticks actually written (dedupe skips don't count). The sync engine
    calls this once per pass, after it has refreshed prices via pull_active."""
    events = db.scalars(
        select(MarketEvent).where(MarketEvent.active.is_(True), MarketEvent.yes_price.is_not(None))
    ).all()
    return sum(1 for event in events if record_tick(db, event) is not None)


def series(db: Session, event_id: int, limit: int = 500) -> list[dict]:
    """The event's price history as [{timestamp, yes_price}], oldest-first.

    Returns at most `limit` points — the most recent ones, so a long-lived
    market's chart shows its latest window — ordered ascending for plotting.
    """
    rows = db.scalars(
        select(PriceTick)
        .where(PriceTick.event_id == event_id)
        .order_by(PriceTick.timestamp.desc(), PriceTick.id.desc())
        .limit(limit)
    ).all()
    rows.reverse()  # newest-N selected desc, emitted ascending
    return [{"timestamp": row.timestamp, "yes_price": row.yes_price} for row in rows]
