"""Related questions, alerts, per-agent records, CSV export."""

import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_related_finds_topical_neighbors(client):
    # Two questions that verifiably share tokens.
    a = client.post(
        "/api/questions",
        json={"question": "Will the related-neighbor alpha probe topic resolve YES this cycle?", "category": "science"},
    ).json()
    b = client.post(
        "/api/questions",
        json={"question": "Will the related-neighbor beta probe topic resolve NO this cycle?", "category": "science"},
    ).json()
    related = client.get(f"/api/questions/{a['id']}/related").json()
    assert any(r["id"] == b["id"] for r in related)
    assert all(r["id"] != a["id"] for r in related)
    sims = [r["similarity"] for r in related]
    assert sims == sorted(sims, reverse=True)


def test_related_unknown_question_404(client):
    assert client.get("/api/questions/99999/related").status_code == 404


def test_alerts_derive_edge_and_move(client):
    items = client.get("/api/alerts?days=3&min_move=0.01&min_edge=0.05").json()
    assert items
    values = [abs(i["value"]) for i in items]
    assert values == sorted(values, reverse=True)
    ids = [i["question_id"] for i in items]
    assert len(ids) == len(set(ids))  # one alert per question
    for item in items:
        assert item["kind"] in {"edge", "move"}
        assert item["detail"]


def test_alerts_thresholds_filter(client):
    strict = client.get("/api/alerts?min_move=0.99&min_edge=0.99").json()
    assert strict == []


def test_agent_records_receipts(client):
    rows = client.get("/api/agents/synthesis/records").json()
    assert rows, "demo resolutions guarantee synthesis records"
    for row in rows:
        assert 0 <= row["probability"] <= 1
        assert row["outcome"] in (0, 1)
        assert row["abs_error"] == pytest.approx(abs(row["probability"] - row["outcome"]), abs=1e-4)
    assert client.get("/api/agents/skeptic/records").status_code == 404  # never estimates
    assert client.get("/api/agents/nonsense/records").status_code == 404


def test_predictions_csv(client):
    resp = client.get("/api/leaderboard/predictions.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("question_id,question,category")
    assert len(lines) >= 40  # header + the seeded corpus at minimum
