"""What-changed diff, unified search, feed RSS, per-agent calibration, metrics."""

import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_changes_after_refresh(client):
    qid = client.get("/api/questions?resolved=false").json()[-1]["id"]
    client.post(f"/api/questions/{qid}/refresh")
    payload = client.get(f"/api/questions/{qid}/changes").json()
    assert payload["from"] is not None and payload["to"] is not None
    assert payload["delta"] == pytest.approx(payload["to"] - payload["from"], abs=1e-3)


def test_changes_single_forecast_is_null(client):
    created = client.post(
        "/api/questions",
        json={"question": "Will the single-forecast changes probe question resolve YES?", "category": "science"},
    ).json()
    payload = client.get(f"/api/questions/{created['id']}/changes").json()
    assert payload["delta"] is None


def test_search_spans_questions_and_archive(client):
    payload = client.get("/api/search?q=NVIDIA").json()
    assert payload["questions"] or payload["archive"]
    assert client.get("/api/search?q=a").status_code == 422  # too short


def test_feed_rss(client):
    resp = client.get("/api/feed/rss")
    assert resp.status_code == 200
    assert "vanta Intelligence Feed" in resp.text


def test_agent_calibration_bins(client):
    bins = client.get("/api/agents/synthesis/calibration").json()
    assert bins and sum(b["count"] for b in bins) >= 2
    assert client.get("/api/agents/nonsense/calibration").status_code == 404


def test_metrics_exposition(client):
    client.get("/api/stats")
    text = client.get("/metrics").text
    assert "vanta_requests_total" in text
    assert 'route="GET /api/stats"' in text
