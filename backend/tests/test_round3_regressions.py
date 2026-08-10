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
    """The 'previous run' must never be a synthetic random-walk snapshot.
    Deterministic setup: seeded questions carry exactly one real run + 30
    backfill rows, so before any refresh the delta must be null; after one
    refresh, 'from' must equal the pre-refresh REAL probability — not
    whichever backfill row happens to sort next."""
    seeded_qid = client.get("/api/questions").json()[-1]["id"]
    history = client.get(f"/api/questions/{seeded_qid}/history").json()
    assert len(history) >= 30  # backfill definitely present
    before = client.get(f"/api/questions/{seeded_qid}/changes").json()
    assert before["delta"] is None and before["from"] is None
    real_prob = client.get(f"/api/questions/{seeded_qid}").json()["latest_forecast"]["probability"]
    client.post(f"/api/questions/{seeded_qid}/refresh")
    after = client.get(f"/api/questions/{seeded_qid}/changes").json()
    assert after["from"] == pytest.approx(real_prob)
    assert after["delta"] == pytest.approx(after["to"] - after["from"], abs=1e-3)


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


def test_brief_rss_has_items(client):
    """Direct-call defaults regression: a Query sentinel leaking into
    morning_brief() emptied every RSS channel while JSON kept working."""
    from app.routers.brief import _local_cache

    _local_cache.clear()
    body = client.get("/api/brief/rss?count=5").text
    assert "<item>" in body
    scoped = client.get("/api/brief/rss?count=5&category=technology").text
    assert "<item>" in scoped
    _local_cache.clear()


def test_brief_category_is_validated(client):
    """'all' collided with the unscoped cache key and poisoned it empty."""
    from app.routers.brief import _local_cache

    _local_cache.clear()
    assert client.get("/api/brief?count=5&category=all").status_code == 422
    assert client.get("/api/brief?count=5&category=nonsense").status_code == 422
    assert len(client.get("/api/brief?count=5").json()) > 0
    _local_cache.clear()


def test_whitespace_note_rejected(client):
    qid = client.get("/api/questions").json()[-1]["id"]
    assert client.post(f"/api/questions/{qid}/notes", json={"body": "   "}).status_code == 422
    created = client.post(f"/api/questions/{qid}/notes", json={"body": "  real note  "})
    assert created.status_code == 201
    assert created.json()["body"] == "real note"
    client.delete(f"/api/questions/{qid}/notes/{created.json()['id']}")
