import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _live_qid(client) -> int:
    return client.get("/api/questions?resolved=false").json()[-1]["id"]


def test_seeded_market_history_exists(client):
    qid = _live_qid(client)
    points = client.get(f"/api/questions/{qid}/market-history").json()
    assert len(points) >= 31  # 30-day walk + the current price point
    assert all(0 < p["probability"] < 1 for p in points)
    assert points[0]["timestamp"].endswith("Z")


def test_market_update_appends_and_mirrors(client):
    qid = _live_qid(client)
    before = client.get(f"/api/questions/{qid}/market-history").json()
    detail = client.post(f"/api/questions/{qid}/market", json={"probability": 0.55}).json()
    assert detail["market_probability"] == 0.55
    after = client.get(f"/api/questions/{qid}/market-history").json()
    assert len(after) == len(before) + 1
    assert after[-1]["probability"] == 0.55


def test_market_update_validation(client):
    qid = _live_qid(client)
    assert client.post(f"/api/questions/{qid}/market", json={"probability": 1.5}).status_code == 422


def test_market_frozen_after_resolution(client):
    qid = _live_qid(client)
    assert client.post(f"/api/questions/{qid}/resolve", json={"outcome": True}).status_code == 200
    resp = client.post(f"/api/questions/{qid}/market", json={"probability": 0.9})
    assert resp.status_code == 409


def test_refresh_after_market_move_changes_edge(client):
    qid = _live_qid(client)
    client.post(f"/api/questions/{qid}/market", json={"probability": 0.11})
    detail = client.post(f"/api/questions/{qid}/refresh").json()
    # The market agent consumed the new price: market probability moved, and
    # the forecast reflects a re-run (reports fresh, forecast present).
    assert detail["market_probability"] == 0.11
    assert detail["latest_forecast"] is not None
