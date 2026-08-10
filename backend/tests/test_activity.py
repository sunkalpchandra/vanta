"""Public activity tape: recent trades across all traders, newest first.

Shares the suite SQLite (conftest binds it before app import). The tape is a
GLOBAL feed, so this module scopes its assertions to its own events (source
'test-w7-activity') and freshly registered users — never to the whole list,
which other modules also write into.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.routers import activity

# Until main.py wires the router (shared file — integration step), mount it here.
# The guard makes this a no-op once main.py includes it, so it can't double-register.
if not any(getattr(r, "path", "").startswith("/api/activity") for r in app.routes):
    app.include_router(activity.router)

DISCLAIMER = "play money · paper trading · real market prices"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _make_event(question: str, yes_price: float = 0.4) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w7-activity",
            source_id=f"w7a-{uuid.uuid4().hex}",
            question=question,
            category="technology",
            active=True,
            yes_price=yes_price,
            outcome=None,
        )
        db.add(event)
        db.commit()
        return event.id


def _trade(client, user, event_id, side, action, shares):
    return client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers={"X-API-Key": user["api_key"]},
    )


def test_envelope_and_note_present(client):
    body = client.get("/api/activity/trades").json()
    assert body["note"] == DISCLAIMER
    assert isinstance(body["trades"], list)  # empty is fine — no crash on a bare feed


def test_trade_appears_newest_first_with_redacted_name(client):
    user = _register(client, "tape")
    local = user["email"].split("@")[0]
    question = f"Will activity probe {uuid.uuid4().hex[:8]} resolve YES?"
    event_id = _make_event(question)

    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200
    assert _trade(client, user, event_id, "yes", "buy", 5).status_code == 200  # placed last

    body = client.get("/api/activity/trades?limit=100").json()
    mine = [t for t in body["trades"] if t["event_id"] == event_id]
    assert len(mine) == 2

    # Newest first: the 5-share buy was the last write.
    assert mine[0]["shares"] == pytest.approx(5)
    assert mine[1]["shares"] == pytest.approx(10)
    # And their positions in the global feed stay newest-first (ascending index).
    idx = [i for i, t in enumerate(body["trades"]) if t["event_id"] == event_id]
    assert idx == sorted(idx)

    row = mine[0]
    assert row["trader"] == local
    assert "@" not in row["trader"]  # full email never leaks
    assert row["question"] == question
    assert row["side"] == "yes"
    assert row["action"] == "buy"
    assert row["price"] == pytest.approx(0.4)
    assert row["event_id"] == event_id
    assert isinstance(row["id"], int)
    assert row["created_at"].endswith("Z") or "+00:00" in row["created_at"]


def test_limit_is_respected_and_bounded(client):
    user = _register(client, "limiter")
    event_id = _make_event(f"Limit probe {uuid.uuid4().hex[:8]}?")
    for _ in range(3):
        assert _trade(client, user, event_id, "yes", "buy", 2).status_code == 200

    # At least our 3 trades exist globally now, so limit=2 must return exactly 2.
    body = client.get("/api/activity/trades?limit=2").json()
    assert len(body["trades"]) == 2

    assert client.get("/api/activity/trades?limit=101").status_code == 422
    assert client.get("/api/activity/trades?limit=0").status_code == 422


def test_agent_trader_shows_agent_name_not_email(client):
    from sqlalchemy import select

    from app.models import AgentTrader, User

    user = _register(client, "botmail")
    agent_name = f"vanta-bot-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        bot_user = db.scalar(select(User).where(User.email == user["email"]))
        db.add(AgentTrader(name=agent_name, strategy="edge", user_id=bot_user.id))
        db.commit()

    event_id = _make_event(f"Bot probe {uuid.uuid4().hex[:8]}?")
    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200

    body = client.get("/api/activity/trades?limit=100").json()
    mine = [t for t in body["trades"] if t["event_id"] == event_id]
    assert mine and mine[0]["trader"] == agent_name
    assert "@" not in mine[0]["trader"]
