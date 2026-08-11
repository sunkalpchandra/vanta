"""Global market search API — substring match over the real-event corpus.

Shares the suite SQLite (conftest binds it before app import). Search is a
GLOBAL query, so every test scopes its matches with a per-test unique token
embedded in the seeded questions (source 'test-w10-search') — that isolates
assertions from the demo seed and other modules' rows without relying on
absolute counts.

main.py doesn't wire this router yet (a shared file — the integration step),
so the router is mounted here. The mount is guarded to a no-op once main.py
includes it, so this suite keeps passing after integration.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.routers import market_search

_MOUNTED = any(getattr(r, "path", None) == "/api/market-search" for r in app.routes)
if not _MOUNTED:
    app.include_router(market_search.router)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(
    question: str,
    *,
    active: bool = True,
    outcome: int | None = None,
    yes_price: float | None = 0.5,
    volume: float = 0.0,
) -> int:
    with SessionLocal() as db:
        ev = MarketEvent(
            source="test-w10-search",
            source_id=f"w10s-{uuid.uuid4().hex}",
            question=question,
            category="technology",
            active=active,
            outcome=outcome,
            yes_price=yes_price,
            volume_usd=volume,
        )
        db.add(ev)
        db.commit()
        return ev.id


def _search(client, q: str, **params) -> dict:
    resp = client.get("/api/market-search", params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_matches_by_substring_and_echoes_query(client):
    token = f"zephyr{uuid.uuid4().hex[:8]}"
    hit = _make_event(f"Will {token} ship alpha in 2027?", active=True)
    _make_event("A wholly unrelated widget market", active=True)  # must not match

    # Case-insensitive substring anywhere in the question.
    body = _search(client, token.upper(), status="all")
    assert body["query"] == token.upper()
    ids = [item["event_id"] for item in body["items"]]
    assert ids == [hit]

    item = body["items"][0]
    assert set(item) == {"event_id", "question", "category", "source", "yes_price", "outcome", "active"}
    assert item["source"] == "test-w10-search"
    assert item["active"] is True
    assert item["outcome"] is None


def test_active_first_then_by_volume(client):
    token = f"rankord{uuid.uuid4().hex[:8]}"
    low_active = _make_event(f"{token} low-volume active", active=True, volume=100.0)
    high_active = _make_event(f"{token} high-volume active", active=True, volume=900.0)
    settled = _make_event(f"{token} settled", active=False, outcome=1, volume=5000.0)

    body = _search(client, token, status="all")
    order = [item["event_id"] for item in body["items"]]
    # Both active rows precede the settled one despite its far larger volume;
    # within active, higher volume first.
    assert order == [high_active, low_active, settled]


def test_status_filter(client):
    token = f"statusf{uuid.uuid4().hex[:8]}"
    active_id = _make_event(f"{token} still open", active=True, outcome=None)
    settled_id = _make_event(f"{token} already resolved", active=False, outcome=0)

    active_ids = [i["event_id"] for i in _search(client, token, status="active")["items"]]
    assert active_ids == [active_id]

    settled_ids = [i["event_id"] for i in _search(client, token, status="settled")["items"]]
    assert settled_ids == [settled_id]

    all_ids = {i["event_id"] for i in _search(client, token, status="all")["items"]}
    assert all_ids == {active_id, settled_id}

    # Default status is active.
    default_ids = [i["event_id"] for i in _search(client, token)["items"]]
    assert default_ids == [active_id]


def test_limit_caps_results(client):
    token = f"limcap{uuid.uuid4().hex[:8]}"
    for i in range(3):
        _make_event(f"{token} candidate {i}", active=True, volume=float(i))

    assert len(_search(client, token, status="all", limit=2)["items"]) == 2
    assert len(_search(client, token, status="all", limit=1)["items"]) == 1
    # No limit param -> all three fit under the default cap.
    assert len(_search(client, token, status="all")["items"]) == 3


def test_short_or_missing_query_is_422(client):
    assert client.get("/api/market-search").status_code == 422  # q required
    assert client.get("/api/market-search", params={"q": ""}).status_code == 422
    assert client.get("/api/market-search", params={"q": "a"}).status_code == 422
    # Exactly the minimum length is accepted.
    assert client.get("/api/market-search", params={"q": "ab"}).status_code == 200


def test_limit_bounds_validation(client):
    assert client.get("/api/market-search", params={"q": "abc", "limit": 0}).status_code == 422
    assert client.get("/api/market-search", params={"q": "abc", "limit": 51}).status_code == 422
    assert client.get("/api/market-search", params={"q": "abc", "status": "bogus"}).status_code == 422
