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


def test_watchlist_list_and_delete(client):
    extra = {"question": "Will a spot commodity ETF double its holdings within a year?", "category": "finance"}
    created = client.post("/api/discover/watchlist", json=extra).json()
    listed = client.get("/api/discover/watchlist").json()
    assert any(w["id"] == created["id"] for w in listed)
    assert client.delete(f"/api/discover/watchlist/{created['id']}").status_code == 204
    assert client.delete(f"/api/discover/watchlist/{created['id']}").status_code == 404
    remaining = client.get("/api/discover/watchlist").json()
    assert all(w["id"] != created["id"] for w in remaining)


def test_watchlist_rejects_builtin_duplicate(client):
    """Regression: adding the exact text of a built-in watchlist candidate
    used to return 201 and mint duplicate questions via discovery."""
    from app.discovery import WATCHLIST

    body = {"question": WATCHLIST[0].question, "category": WATCHLIST[0].category}
    assert client.post("/api/discover/watchlist", json=body).status_code == 409


def test_watchlist_rejects_already_covered_question(client):
    text = client.get("/api/questions").json()[-1]["question"]
    resp = client.post("/api/discover/watchlist", json={"question": text, "category": "finance"})
    assert resp.status_code == 409


def test_calibration_category_filter(client):
    finance = client.get("/api/leaderboard/calibration?category=finance").json()
    everything = client.get("/api/leaderboard/calibration").json()
    assert sum(b["vanta_count"] for b in finance) < sum(b["vanta_count"] for b in everything)
    assert client.get("/api/leaderboard/calibration?category=nonexistent").json() == []


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
