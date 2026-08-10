"""Per-trader market watchlist + 24h move alerts.

Shares the suite SQLite (conftest binds it before app import). Every row this
module writes is scoped to the unique source 'test-w8-watch', and each test
registers its own trader, so other modules' writes never matter here.

main.py wiring the router is the integration step, so this module mounts it
onto the shared app itself — guarded so it's a no-op once main.py includes it.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent, PriceTick, utcnow

SOURCE = "test-w8-watch"


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


def _make_event(yes_price: float | None = 0.5, active: bool = True, outcome: int | None = None) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source=SOURCE,
            source_id=f"w-{uuid.uuid4().hex}",
            question=f"Will watch-market {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=active,
            yes_price=yes_price,
            outcome=outcome,
        )
        db.add(event)
        db.commit()
        return event.id


def _add_tick(event_id: int, yes_price: float, hours_ago: float) -> None:
    with SessionLocal() as db:
        db.add(
            PriceTick(
                event_id=event_id,
                yes_price=yes_price,
                timestamp=utcnow() - timedelta(hours=hours_ago),
            )
        )
        db.commit()


# --- identity -----------------------------------------------------------------


def test_watch_endpoints_require_a_valid_key(client):
    event_id = _make_event()
    assert client.post(f"/api/watch/{event_id}").status_code == 401
    assert client.get("/api/watch").status_code == 401
    assert client.delete(f"/api/watch/{event_id}").status_code == 401
    bogus = {"X-API-Key": "vk_bogus"}
    assert client.post(f"/api/watch/{event_id}", headers=bogus).status_code == 401
    assert client.get("/api/watch", headers=bogus).status_code == 401


# --- add / idempotence / 404 --------------------------------------------------


def test_add_is_idempotent_and_appears_in_list(client):
    user = _register(client, "watcher")
    event_id = _make_event(yes_price=0.5)

    first = client.post(f"/api/watch/{event_id}", headers=_auth(user))
    assert first.status_code == 201
    assert first.json() == {"event_id": event_id, "watched": True, "created": True}

    again = client.post(f"/api/watch/{event_id}", headers=_auth(user))
    assert again.status_code == 200
    assert again.json() == {"event_id": event_id, "watched": True, "created": False}

    listed = client.get("/api/watch", headers=_auth(user)).json()
    row = next(w for w in listed if w["event_id"] == event_id)
    assert row["yes_price"] == pytest.approx(0.5)
    assert row["delta_24h"] is None  # no ticks yet → no computed move
    assert row["moved"] is False


def test_watch_unknown_event_is_404(client):
    user = _register(client, "ghost")
    assert client.post("/api/watch/99999999", headers=_auth(user)).status_code == 404


# --- remove -------------------------------------------------------------------


def test_unwatch_removes_and_second_delete_is_404(client):
    user = _register(client, "unwatcher")
    event_id = _make_event()
    assert client.post(f"/api/watch/{event_id}", headers=_auth(user)).status_code == 201

    assert client.delete(f"/api/watch/{event_id}", headers=_auth(user)).status_code == 204
    assert client.delete(f"/api/watch/{event_id}", headers=_auth(user)).status_code == 404

    listed = client.get("/api/watch", headers=_auth(user)).json()
    assert all(w["event_id"] != event_id for w in listed)


# --- move computation ---------------------------------------------------------


def test_moved_flag_uses_earliest_tick_inside_window(client):
    user = _register(client, "mover")

    # Big move: an out-of-window tick must be ignored; earliest in-window is 0.40.
    moved_id = _make_event(yes_price=0.55)
    _add_tick(moved_id, 0.90, hours_ago=30)  # older than 24h → excluded
    _add_tick(moved_id, 0.40, hours_ago=6)  # earliest in-window
    _add_tick(moved_id, 0.50, hours_ago=1)

    # Small move: 0.41 vs 0.40 → +0.01, under threshold.
    calm_id = _make_event(yes_price=0.41)
    _add_tick(calm_id, 0.40, hours_ago=6)

    # Boundary: 0.45 vs 0.40 → exactly 0.05 → moved (>=), despite float drift.
    edge_id = _make_event(yes_price=0.45)
    _add_tick(edge_id, 0.40, hours_ago=3)

    # No synced price → no delta even with a tick present.
    dark_id = _make_event(yes_price=None)
    _add_tick(dark_id, 0.40, hours_ago=2)

    for event_id in (moved_id, calm_id, edge_id, dark_id):
        assert client.post(f"/api/watch/{event_id}", headers=_auth(user)).status_code == 201

    rows = {w["event_id"]: w for w in client.get("/api/watch", headers=_auth(user)).json()}

    assert rows[moved_id]["delta_24h"] == pytest.approx(0.15)
    assert rows[moved_id]["moved"] is True

    assert rows[calm_id]["delta_24h"] == pytest.approx(0.01)
    assert rows[calm_id]["moved"] is False

    assert rows[edge_id]["delta_24h"] == pytest.approx(0.05)
    assert rows[edge_id]["moved"] is True

    assert rows[dark_id]["delta_24h"] is None
    assert rows[dark_id]["moved"] is False


# --- isolation / redaction ----------------------------------------------------


def test_watchlist_is_per_trader_and_leaks_no_identity(client):
    alice = _register(client, "alice")
    bob = _register(client, "bob")
    a_event = _make_event()
    b_event = _make_event()
    assert client.post(f"/api/watch/{a_event}", headers=_auth(alice)).status_code == 201
    assert client.post(f"/api/watch/{b_event}", headers=_auth(bob)).status_code == 201

    a_rows = client.get("/api/watch", headers=_auth(alice)).json()
    a_ids = [w["event_id"] for w in a_rows]
    assert a_event in a_ids
    assert b_event not in a_ids  # another trader's watch never surfaces

    # Response is market signal only — no user_id / email / api_key leaks.
    row = next(w for w in a_rows if w["event_id"] == a_event)
    assert set(row.keys()) == {"event_id", "question", "yes_price", "delta_24h", "moved"}
