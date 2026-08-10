"""Public trader profiles: leaderboard mirror + a per-trader book by handle.

Shares the suite SQLite (conftest binds it before app import). The leaderboard
is a GLOBAL feed, so assertions are scoped to this module's own events (source
'test-w8-profile') and freshly registered users — never to the whole list,
which other modules also write into.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent

DISCLAIMER = "play money · paper trading · real market prices"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _make_event(yes_price: float = 0.4, question: str | None = None) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w8-profile",
            source_id=f"w8p-{uuid.uuid4().hex}",
            question=question or f"Will profile probe {uuid.uuid4().hex[:8]} resolve YES?",
            category="technology",
            active=True,
            yes_price=yes_price,
            outcome=None,
        )
        db.add(event)
        db.commit()
        return event.id


def _set_price(event_id: int, yes_price: float) -> None:
    with SessionLocal() as db:
        db.get(MarketEvent, event_id).yes_price = yes_price
        db.commit()


def _trade(client, user, event_id, side, action, shares):
    return client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers={"X-API-Key": user["api_key"]},
    )


# --- leaderboard mirror -------------------------------------------------------


def test_leaderboard_mirrors_markets_traders_shape(client):
    body = client.get("/api/traders").json()
    assert body["note"] == DISCLAIMER
    assert isinstance(body["traders"], list)  # empty is fine on a bare feed
    # Same envelope as /api/markets/traders: the two must not diverge.
    mirror = client.get("/api/markets/traders").json()
    assert set(body) == set(mirror)


def test_leaderboard_limit_is_bounded(client):
    assert client.get("/api/traders?limit=101").status_code == 422
    assert client.get("/api/traders?limit=0").status_code == 422


# --- profile ------------------------------------------------------------------


def test_profile_resolves_by_handle_and_redacts(client):
    user = _register(client, "profile")
    handle = user["email"].split("@")[0]
    question = f"Will handle probe {uuid.uuid4().hex[:8]} resolve YES?"
    event_id = _make_event(yes_price=0.4, question=question)
    assert _trade(client, user, event_id, "yes", "buy", 100).status_code == 200

    body = client.get(f"/api/traders/{handle}").json()
    assert body["name"] == handle
    assert "@" not in body["name"]
    # Full email + credential never leave the endpoint.
    dumped = str(body)
    assert user["email"] not in dumped
    assert user["api_key"] not in dumped
    assert "email" not in body and "api_key" not in body

    assert body["note"] == DISCLAIMER
    assert body["n_trades"] == 1
    assert body["balance"] == pytest.approx(9960.0)  # 100 × ⓥ0.40
    assert body["joined"].endswith("Z") or "+00:00" in body["joined"]

    mine = [p for p in body["positions"] if p["event_id"] == event_id]
    assert len(mine) == 1
    pos = mine[0]
    assert set(pos) == {
        "event_id", "question", "side", "shares", "avg_price",
        "current_price", "unrealized_pnl", "settled",
    }
    assert pos["question"] == question
    assert pos["side"] == "yes"
    assert pos["shares"] == pytest.approx(100)
    assert pos["avg_price"] == pytest.approx(0.4)
    assert pos["settled"] is False

    trades = [t for t in body["recent_trades"] if t["event_id"] == event_id]
    assert len(trades) == 1
    tr = trades[0]
    assert set(tr) == {"event_id", "question", "side", "action", "shares", "price", "created_at"}
    assert tr["action"] == "buy"
    assert tr["price"] == pytest.approx(0.4)
    assert tr["created_at"].endswith("Z") or "+00:00" in tr["created_at"]


def test_profile_marks_positions_and_equity(client):
    user = _register(client, "marks")
    event_id = _make_event(yes_price=0.4)
    _trade(client, user, event_id, "yes", "buy", 50)  # cost ⓥ20 -> 9980
    _set_price(event_id, 0.6)  # YES now worth 0.6

    body = client.get(f"/api/traders/{user['email'].split('@')[0]}").json()
    pos = next(p for p in body["positions"] if p["event_id"] == event_id)
    assert pos["current_price"] == pytest.approx(0.6)
    assert pos["unrealized_pnl"] == pytest.approx(10.0)  # 50 × (0.6 - 0.4)
    # equity = balance + market value of the open lot = 9980 + 50 × 0.6
    assert body["balance"] == pytest.approx(9980.0)
    assert body["equity"] == pytest.approx(10_010.0)


def test_profile_newest_trade_first(client):
    user = _register(client, "order")
    event_id = _make_event(yes_price=0.4)
    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200
    assert _trade(client, user, event_id, "yes", "buy", 5).status_code == 200  # placed last

    body = client.get(f"/api/traders/{user['email'].split('@')[0]}").json()
    mine = [t for t in body["recent_trades"] if t["event_id"] == event_id]
    assert [t["shares"] for t in mine] == [pytest.approx(5), pytest.approx(10)]
    assert body["n_trades"] == 2


def test_unknown_handle_is_404(client):
    assert client.get(f"/api/traders/nobody-{uuid.uuid4().hex[:10]}").status_code == 404


def test_handle_collision_resolves_first_by_id(client):
    handle = f"collide-{uuid.uuid4().hex[:8]}"
    first = client.post("/api/users", json={"email": f"{handle}@a.test"}).json()
    second = client.post("/api/users", json={"email": f"{handle}@b.test"}).json()
    assert first["id"] < second["id"]

    # Both must have traded to have a public profile (never-traded accounts
    # 404 — no balance enumeration). Give them distinct balances via trades.
    event = _make_event(0.4)
    _trade(client, first, event, "yes", "buy", 10)  # first spends ⓥ4
    _trade(client, second, event, "yes", "buy", 100)  # second spends ⓥ40

    body = client.get(f"/api/traders/{handle}").json()
    assert body["name"] == handle  # both share the handle; the endpoint returns one
    # First-by-id wins deterministically: the lower-id registration's book shows.
    assert body["balance"] == pytest.approx(9996.0)  # 10000 - 4


def test_never_traded_handle_is_not_enumerable(client):
    handle = f"idle-{uuid.uuid4().hex[:8]}"
    client.post("/api/users", json={"email": f"{handle}@a.test"})
    # Registered but never traded -> 404, so balances can't be enumerated.
    assert client.get(f"/api/traders/{handle}").status_code == 404
