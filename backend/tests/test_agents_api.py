import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_agent_leaderboard_populated_by_demo_resolutions(client):
    rows = client.get("/api/agents/leaderboard").json()
    agents = {r["agent"] for r in rows}
    # Estimators always carry a probability; the skeptic never does.
    assert {"research", "market", "historian", "synthesis"} <= agents
    assert "skeptic" not in agents
    for row in rows:
        assert row["n_resolved"] >= 2  # the two seed-time demo resolutions
        assert 0 <= row["accuracy"] <= 1
        assert 0 <= row["brier"] <= 1
        assert row["log_score"] > 0


def test_agent_leaderboard_sorted_by_brier(client):
    rows = client.get("/api/agents/leaderboard").json()
    briers = [r["brier"] for r in rows]
    assert briers == sorted(briers)


def test_demo_resolutions_visible_in_archive(client):
    resolved = client.get("/api/questions?resolved=true").json()
    texts = {q["question"] for q in resolved}
    assert "Will the favorite win the NBA championship this season?" in texts
    predictions = client.get("/api/leaderboard/predictions").json()
    linked = [p for p in predictions if p["question_id"] is not None]
    assert len(linked) >= 2


def test_resolving_grows_agent_track_records(client):
    before = {r["agent"]: r["n_resolved"] for r in client.get("/api/agents/leaderboard").json()}
    live = client.get("/api/questions?resolved=false").json()
    qid = live[-1]["id"]
    assert client.post(f"/api/questions/{qid}/resolve", json={"outcome": False}).status_code == 200
    after = {r["agent"]: r["n_resolved"] for r in client.get("/api/agents/leaderboard").json()}
    assert after["synthesis"] == before["synthesis"] + 1
