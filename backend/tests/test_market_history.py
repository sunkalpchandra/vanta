"""Market price-history capture + read API.

Shares the suite SQLite (conftest binds it before app import). Every event is
seeded under a unique source ('test-w7-hist') so other modules' writes never
collide, and price ticks are scoped to those events.

Until main.py wires the market-history router (a shared file, handled in the
integration step), mount it onto the app here — a no-op once main includes it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent, PriceTick
from app.pricehistory import record_tick, record_ticks_for_active, series
from app.routers import market_history

_HISTORY_PATH = "/api/markets/{event_id}/history"
if not any(getattr(r, "path", None) == _HISTORY_PATH for r in app.router.routes):
    app.include_router(market_history.router)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(yes_price=0.4, active=True, outcome=None) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w7-hist",
            source_id=f"w7h-{uuid.uuid4().hex}",
            question=f"Will history probe {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=active,
            yes_price=yes_price,
            outcome=outcome,
        )
        db.add(event)
        db.commit()
        return event.id


def _backdate_latest(event_id: int, *, hours: float) -> None:
    """Age the newest tick for an event so record_tick sees it as > 1h old —
    stands in for the passage of time within a single test run."""
    with SessionLocal() as db:
        tick = db.scalar(
            select(PriceTick)
            .where(PriceTick.event_id == event_id)
            .order_by(PriceTick.timestamp.desc(), PriceTick.id.desc())
            .limit(1)
        )
        tick.timestamp = datetime.now(UTC) - timedelta(hours=hours)
        db.commit()


def _set_price(event_id: int, yes_price: float) -> None:
    with SessionLocal() as db:
        db.get(MarketEvent, event_id).yes_price = yes_price
        db.commit()


def _count_ticks(event_id: int) -> int:
    with SessionLocal() as db:
        return len(db.scalars(select(PriceTick).where(PriceTick.event_id == event_id)).all())


# --- record_tick: dedupe ------------------------------------------------------


def test_first_tick_writes_repeat_within_hour_skips(client):
    event_id = _make_event(yes_price=0.4)
    with SessionLocal() as db:
        event = db.get(MarketEvent, event_id)
        first = record_tick(db, event)
        assert first is not None
        assert first.yes_price == pytest.approx(0.4)
        # Same price, same hour -> skipped (both dedupe reasons apply).
        assert record_tick(db, event) is None
    assert _count_ticks(event_id) == 1


def test_price_change_after_hour_writes_second_row(client):
    event_id = _make_event(yes_price=0.4)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None
    assert _count_ticks(event_id) == 1

    # Age the only tick past the hour window and move the price.
    _backdate_latest(event_id, hours=2)
    _set_price(event_id, 0.55)
    with SessionLocal() as db:
        second = record_tick(db, db.get(MarketEvent, event_id))
        assert second is not None
        assert second.yes_price == pytest.approx(0.55)
    assert _count_ticks(event_id) == 2


def test_same_price_after_hour_still_skips(client):
    event_id = _make_event(yes_price=0.3)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None
    # An hour passes but the price hasn't moved -> the same-price branch skips.
    _backdate_latest(event_id, hours=2)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is None
    assert _count_ticks(event_id) == 1


def test_event_without_price_records_nothing(client):
    event_id = _make_event(yes_price=None)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is None
    assert _count_ticks(event_id) == 0


# --- record_ticks_for_active --------------------------------------------------


def test_record_ticks_for_active_counts_new_writes(client):
    a = _make_event(yes_price=0.2)
    b = _make_event(yes_price=0.7)
    inactive = _make_event(yes_price=0.5, active=False)
    priceless = _make_event(yes_price=None)

    with SessionLocal() as db:
        written = record_ticks_for_active(db)
    # At least our two active-with-price events were captured this pass. Other
    # modules may have active events too, so assert a lower bound.
    assert written >= 2
    assert _count_ticks(a) == 1
    assert _count_ticks(b) == 1
    assert _count_ticks(inactive) == 0
    assert _count_ticks(priceless) == 0

    # Re-run immediately: everything is within the hour, so nothing new is
    # written for our events.
    with SessionLocal() as db:
        record_ticks_for_active(db)
    assert _count_ticks(a) == 1
    assert _count_ticks(b) == 1


# --- series -------------------------------------------------------------------


def test_series_is_ascending(client):
    event_id = _make_event(yes_price=0.4)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None
    _backdate_latest(event_id, hours=3)
    _set_price(event_id, 0.5)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None

    with SessionLocal() as db:
        points = series(db, event_id)
    assert [p["yes_price"] for p in points] == [pytest.approx(0.4), pytest.approx(0.5)]
    stamps = [p["timestamp"].replace(tzinfo=UTC) if p["timestamp"].tzinfo is None else p["timestamp"] for p in points]
    assert stamps == sorted(stamps)


def test_series_limit_returns_most_recent(client):
    event_id = _make_event(yes_price=0.10)
    # Lay down three distinct, hour-separated ticks: 0.10, 0.20, 0.30.
    for price in (0.10, 0.20, 0.30):
        _set_price(event_id, price)
        with SessionLocal() as db:
            assert record_tick(db, db.get(MarketEvent, event_id)) is not None
        _backdate_latest(event_id, hours=2)
    with SessionLocal() as db:
        limited = series(db, event_id, limit=2)
    # Most recent two, still ascending. The backdated third is the newest write.
    assert len(limited) == 2
    assert [p["yes_price"] for p in limited] == [pytest.approx(0.20), pytest.approx(0.30)]


# --- endpoint -----------------------------------------------------------------


def test_history_endpoint_returns_points(client):
    event_id = _make_event(yes_price=0.42)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None

    resp = client.get(f"/api/markets/{event_id}/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["event_id"] == event_id
    assert len(body["points"]) == 1
    point = body["points"][0]
    assert point["yes_price"] == pytest.approx(0.42)
    assert point["timestamp"].endswith("Z")  # zone-qualified UTC


def test_history_endpoint_empty_points_allowed(client):
    event_id = _make_event(yes_price=0.5)  # seeded, but no ticks captured
    resp = client.get(f"/api/markets/{event_id}/history")
    assert resp.status_code == 200
    assert resp.json() == {"event_id": event_id, "points": []}


def test_history_endpoint_unknown_id_404(client):
    resp = client.get("/api/markets/999999999/history")
    assert resp.status_code == 404


def test_history_route_does_not_shadow_market_detail(client):
    """The shared /api/markets prefix: /{event_id} and /{event_id}/history must
    both resolve to their own handlers."""
    event_id = _make_event(yes_price=0.33)
    with SessionLocal() as db:
        assert record_tick(db, db.get(MarketEvent, event_id)) is not None

    detail = client.get(f"/api/markets/{event_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == event_id  # existing market-detail handler
    assert "yes_price" in detail.json()

    history = client.get(f"/api/markets/{event_id}/history")
    assert history.status_code == 200
    assert history.json()["event_id"] == event_id  # our history handler
    assert isinstance(history.json()["points"], list)
