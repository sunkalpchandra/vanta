import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py

ITEM = {
    "question": "Will a commercial airline operate a scheduled electric flight route this decade?",
    "category": "technology",
    "horizon_days": 400,
    "rationale": "Two certification programs entered final review.",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_watchlist_add_and_surface(client):
    assert client.post("/api/discover/watchlist", json=ITEM).status_code == 201
    candidates = client.get("/api/discover/candidates").json()
    assert any(c["question"] == ITEM["question"] for c in candidates)


def test_watchlist_rejects_duplicates(client):
    assert client.post("/api/discover/watchlist", json=ITEM).status_code == 409


def test_watchlist_item_flows_through_discovery(client):
    # Mint until our item comes through (user items are queued first).
    created = client.post("/api/discover?count=1").json()
    assert created and created[0]["question"]["question"] == ITEM["question"]
    detail = client.get(f"/api/questions/{created[0]['question']['id']}").json()
    assert detail["latest_forecast"] is not None


def test_feed_sort_options(client):
    by_conf = client.get("/api/feed?sort=confidence").json()
    confs = [c["confidence"] for c in by_conf]
    assert confs == sorted(confs, reverse=True)
    assert client.get("/api/feed?sort=bogus").status_code == 422


def test_brief_rss(client):
    resp = client.get("/api/brief/rss")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/rss+xml")
    assert "<rss" in resp.text and "vanta Morning Brief" in resp.text


def test_quant_backtest_endpoint(client):
    result = client.get("/api/quant/backtest").json()
    assert result["n_events"] >= 30
    assert 0 < result["coverage"] <= 1
    assert result["baseline_brier"] > 0
