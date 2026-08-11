"""Portfolio equity-over-time API — cash flow reconstructed from the Trade log.

Shares the suite SQLite (conftest binds it before app import). Every event is
seeded under a unique source ('test-w9-equity') so other modules' writes never
collide, and users are freshly registered per test.

Until main.py wires the portfolio-history router (a shared file, handled in the
integration step), mount it onto the app here — a no-op once main includes it.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.trading import STARTING_BALANCE

_EQUITY_PATH = "/api/portfolio/equity"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _auth(user: dict) -> dict:
    return {"X-API-Key": user["api_key"]}


def _make_event(yes_price=0.4) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w9-equity",
            source_id=f"w9e-{uuid.uuid4().hex}",
            question=f"Will equity probe {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=True,
            yes_price=yes_price,
        )
        db.add(event)
        db.commit()
        return event.id


def _set_price(event_id: int, yes_price: float) -> None:
    with SessionLocal() as db:
        db.get(MarketEvent, event_id).yes_price = yes_price
        db.commit()


def _trade(client, user, event_id, side, action, shares) -> dict:
    resp = client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers=_auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_equity_requires_key(client):
    assert client.get(_EQUITY_PATH).status_code == 401
    assert client.get(_EQUITY_PATH, headers={"X-API-Key": "vk_bogus"}).status_code == 401


def test_opening_point_only_before_any_trade(client):
    user = _register(client, "fresh")
    body = client.get(_EQUITY_PATH, headers=_auth(user)).json()
    assert body["starting_balance"] == pytest.approx(STARTING_BALANCE)
    # No trades yet: a single opening point at the full starting grant.
    assert len(body["points"]) == 1
    assert body["points"][0]["cash"] == pytest.approx(STARTING_BALANCE)
    assert "settlement" in body["basis"]


def test_buy_then_sell_traces_cash_debit_then_credit(client):
    user = _register(client, "trader")
    event_id = _make_event(yes_price=0.4)

    _trade(client, user, event_id, "yes", "buy", 100)  # cost 40 -> cash 9960
    _set_price(event_id, 0.6)
    _trade(client, user, event_id, "yes", "sell", 50)  # proceeds 30 -> cash 9990

    body = client.get(_EQUITY_PATH, headers=_auth(user)).json()
    cash = [p["cash"] for p in body["points"]]
    # opening grant, then debit on the buy, then credit on the sell.
    assert cash == [
        pytest.approx(STARTING_BALANCE),
        pytest.approx(9960.0),
        pytest.approx(9990.0),
    ]
    assert body["starting_balance"] == pytest.approx(STARTING_BALANCE)


def test_timestamps_are_monotonic_non_decreasing(client):
    user = _register(client, "clock")
    event_id = _make_event(yes_price=0.4)
    _trade(client, user, event_id, "yes", "buy", 100)
    _set_price(event_id, 0.5)
    _trade(client, user, event_id, "yes", "buy", 20)

    body = client.get(_EQUITY_PATH, headers=_auth(user)).json()
    stamps = [p["timestamp"] for p in body["points"]]
    assert len(stamps) == 3
    # ISO-8601 UTC ("...Z") stamps sort lexicographically == chronologically.
    assert all(s.endswith("Z") for s in stamps)
    assert stamps == sorted(stamps)


def test_series_is_scoped_to_the_caller(client):
    a = _register(client, "alice")
    b = _register(client, "bob")
    event_id = _make_event(yes_price=0.4)
    _trade(client, a, event_id, "yes", "buy", 100)  # only Alice trades

    bob_body = client.get(_EQUITY_PATH, headers=_auth(b)).json()
    # Bob never traded: just his opening grant, none of Alice's cash moves.
    assert [p["cash"] for p in bob_body["points"]] == [pytest.approx(STARTING_BALANCE)]
