"""On-demand market forecast + agent debate: service + endpoint coverage.

Shares the suite SQLite (conftest binds it before app import). Every event is
seeded under a unique source ('test-w8-forecast') so other modules' writes
never collide.

Until main.py wires the forecast router (a shared file, handled in the
integration step), mount it — plus the market-history router the shadow test
needs — onto the app here. Both includes are no-ops once main includes them.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.market_forecast import AGREE_BAND, DISAGREE_BAND, forecast_market
from app.models import MarketEvent


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(*, yes_price=0.4, active=True, category="technology", close_in_days=200) -> int:
    close_time = (
        datetime.now(UTC) + timedelta(days=close_in_days) if close_in_days is not None else None
    )
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w8-forecast",
            source_id=f"w8f-{uuid.uuid4().hex}",
            question=f"Will forecast probe {uuid.uuid4().hex[:6]} resolve YES?",
            category=category,
            active=active,
            yes_price=yes_price,
            volume_usd=250_000.0,
            close_time=close_time,
        )
        db.add(event)
        db.commit()
        return event.id


def _expected_direction(edge: float) -> str:
    magnitude = abs(edge)
    if magnitude >= DISAGREE_BAND:
        return "disagree"
    if magnitude < AGREE_BAND:
        return "agree"
    return "neutral"


# --- forecast_market (service) ------------------------------------------------


def test_forecast_shape_and_bounds(client):
    event_id = _make_event(yes_price=0.4)
    with SessionLocal() as db:
        result = forecast_market(db, db.get(MarketEvent, event_id))

    assert 0.0 <= result["probability"] <= 1.0
    assert result["market_probability"] == pytest.approx(0.4)
    assert result["direction"] in {"agree", "disagree", "neutral"}
    assert isinstance(result["risk_factors"], list)
    assert isinstance(result["reasoning"], str) and result["reasoning"]

    reports = result["agent_reports"]
    assert reports, "the agent debate must not be empty"
    # Every report carries the debate fields; the synthesis (final) call and at
    # least one abstaining estimator (quant with no analog corpus) are present.
    for r in reports:
        assert set(r) == {"agent", "stance", "probability", "argument"}
        assert r["stance"] in {"bull", "bear", "neutral"}
    agents = {r["agent"] for r in reports}
    assert {"research", "quant", "market", "sentiment", "historian", "skeptic", "synthesis"} <= agents
    # At least one agent actually estimates (probability is not None) — a real
    # debate, not all-abstain.
    assert any(r["probability"] is not None for r in reports)


def test_forecast_is_deterministic(client):
    event_id = _make_event(yes_price=0.4)
    with SessionLocal() as db:
        first = forecast_market(db, db.get(MarketEvent, event_id))
    with SessionLocal() as db:
        second = forecast_market(db, db.get(MarketEvent, event_id))
    assert first == second


def test_edge_is_probability_minus_price_and_direction_tracks_it(client):
    # A low venue price: vanta, pulled toward the category base rate, reads
    # higher -> positive edge. Its mirror at a high price reads lower.
    low_id = _make_event(yes_price=0.05)
    high_id = _make_event(yes_price=0.95)
    with SessionLocal() as db:
        low = forecast_market(db, db.get(MarketEvent, low_id))
        high = forecast_market(db, db.get(MarketEvent, high_id))

    # edge is exactly the returned probability minus the venue price.
    assert low["edge"] == pytest.approx(round(low["probability"] - 0.05, 4))
    assert high["edge"] == pytest.approx(round(high["probability"] - 0.95, 4))
    # Signs: below-the-middle price -> vanta above (edge > 0); above -> below.
    assert low["edge"] > 0
    assert high["edge"] < 0
    # direction is derived from the edge bands, not invented.
    assert low["direction"] == _expected_direction(low["edge"])
    assert high["direction"] == _expected_direction(high["edge"])


# --- endpoint -----------------------------------------------------------------


def test_forecast_endpoint_200(client):
    event_id = _make_event(yes_price=0.4)
    resp = client.get(f"/api/markets/{event_id}/forecast")
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["probability"] <= 1.0
    assert body["market_probability"] == pytest.approx(0.4)
    assert body["edge"] == pytest.approx(round(body["probability"] - 0.4, 4))
    assert body["direction"] in {"agree", "disagree", "neutral"}
    assert body["agent_reports"]


def test_forecast_endpoint_unknown_id_404(client):
    resp = client.get("/api/markets/999999999/forecast")
    assert resp.status_code == 404


def test_forecast_endpoint_no_price_409(client):
    event_id = _make_event(yes_price=None)
    resp = client.get(f"/api/markets/{event_id}/forecast")
    assert resp.status_code == 409
    assert "no synced price" in resp.json()["detail"]


def test_forecast_route_does_not_shadow_detail_or_history(client):
    """The shared /api/markets prefix: /{event_id}, /{event_id}/history, and
    /{event_id}/forecast must each resolve to their own handler."""
    event_id = _make_event(yes_price=0.33)

    detail = client.get(f"/api/markets/{event_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == event_id
    assert "no_price" in detail.json()  # the market-detail handler, not ours

    history = client.get(f"/api/markets/{event_id}/history")
    assert history.status_code == 200
    assert "points" in history.json()  # the history handler

    forecast = client.get(f"/api/markets/{event_id}/forecast")
    assert forecast.status_code == 200
    assert "agent_reports" in forecast.json()  # our forecast handler
