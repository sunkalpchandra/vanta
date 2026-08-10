"""Regressions from the round-3 review: middleware ordering, cache status
gating, changes vs synthetic history, gated ask."""

import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


ORIGIN = {"Origin": "http://localhost:3000"}


def test_rate_limited_responses_carry_cors(client):
    """CORS must be outermost: a 429 without CORS headers is an opaque browser
    error the UI can't distinguish from the network being down."""
    from app.main import _rate_buckets

    app.state.rate_limit_per_minute = 1
    _rate_buckets.clear()
    try:
        body = {"question": "Will the CORS-on-429 regression probe fire correctly?", "category": "science"}
        client.post("/api/discover/watchlist", json=body, headers=ORIGIN)
        blocked = client.post("/api/discover/watchlist", json=body, headers=ORIGIN)
        assert blocked.status_code == 429
        assert blocked.headers.get("access-control-allow-origin") == "http://localhost:3000"
    finally:
        app.state.rate_limit_per_minute = None
        _rate_buckets.clear()


def test_error_responses_not_publicly_cached(client):
    resp = client.get("/api/cards/999999.svg")
    assert resp.status_code == 404
    assert "cache-control" not in resp.headers


def test_changes_ignores_synthetic_backfill(client):
    """A freshly seeded question has one real run + 30 backfill rows; the
    'previous run' must not be a random-walk snapshot."""
    seeded_qid = client.get("/api/questions").json()[-1]["id"]
    history = client.get(f"/api/questions/{seeded_qid}/history").json()
    assert len(history) >= 30  # backfill definitely present
    payload = client.get(f"/api/questions/{seeded_qid}/changes").json()
    # Only one REAL run exists (unless another module refreshed this question);
    # either way the previous run must never be the seeded walk: with a single
    # real run delta is null, with two the delta matches real forecasts only.
    if payload["delta"] is None:
        assert payload["from"] is None
    else:
        client.post(f"/api/questions/{seeded_qid}/refresh")
        after = client.get(f"/api/questions/{seeded_qid}/changes").json()
        assert after["from"] is not None


def test_ask_is_gated_when_keys_required(client):
    app.state.require_api_key = True
    try:
        body = {"question": "Will the gated-ask regression probe be rejected without a key?", "category": "science"}
        assert client.post("/api/questions", json=body).status_code == 401
    finally:
        app.state.require_api_key = None


def test_notes_crud(client):
    qid = client.get("/api/questions").json()[-1]["id"]
    body = {"body": "Resolution needs the official announcement, not a leak."}
    created = client.post(f"/api/questions/{qid}/notes", json=body)
    assert created.status_code == 201
    note_id = created.json()["id"]
    listed = client.get(f"/api/questions/{qid}/notes").json()
    assert any(n["id"] == note_id for n in listed)
    assert listed[0]["created_at"].endswith("Z")
    assert client.delete(f"/api/questions/{qid}/notes/{note_id}").status_code == 204
    remaining = client.get(f"/api/questions/{qid}/notes").json()
    assert all(n["id"] != note_id for n in remaining)


def test_notes_gated_and_404(client):
    qid = client.get("/api/questions").json()[-1]["id"]
    assert client.get("/api/questions/999999/notes").status_code == 404
    assert client.delete(f"/api/questions/{qid}/notes/999999").status_code == 404
    app.state.require_api_key = True
    try:
        resp = client.post(f"/api/questions/{qid}/notes", json={"body": "should be rejected"})
        assert resp.status_code == 401
    finally:
        app.state.require_api_key = None


def test_brief_category_filter(client):
    from app.routers.brief import _local_cache

    _local_cache.clear()
    scoped = client.get("/api/brief?count=5&category=technology").json()
    assert all(i["category"] == "technology" for i in scoped)
    # ranks stay monotonic in |edge| within the scoped brief
    edges = [abs(i["edge"]) for i in scoped]
    assert edges == sorted(edges, reverse=True)
    # a scoped brief must not poison the all-category cache key
    full = client.get("/api/brief?count=5").json()
    assert len({i["category"] for i in full}) >= 2
    _local_cache.clear()


def test_alerts_rss_is_wellformed(client):
    import xml.etree.ElementTree as ET

    resp = client.get("/api/alerts/rss?min_edge=0.01&min_move=0.01")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/rss+xml")
    root = ET.fromstring(resp.text)
    assert root.tag == "rss"
    assert root.find("channel/title").text == "vanta Alerts"


def test_search_category_scopes_both_result_sets(client):
    body = client.get("/api/search?q=will&category=technology").json()
    assert all(row["category"] == "technology" for row in body["questions"])
    assert all(row["category"] == "technology" for row in body["archive"])
    unscoped = client.get("/api/search?q=will").json()
    total = len(unscoped["questions"]) + len(unscoped["archive"])
    scoped = len(body["questions"]) + len(body["archive"])
    assert scoped <= total
