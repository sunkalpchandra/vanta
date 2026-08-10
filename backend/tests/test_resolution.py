import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def resolved_qid(client):
    qid = client.get("/api/questions").json()[0]["id"]
    resp = client.post(f"/api/questions/{qid}/resolve", json={"outcome": True})
    assert resp.status_code == 200
    return qid


def test_resolve_marks_question(client, resolved_qid):
    detail = client.get(f"/api/questions/{resolved_qid}").json()
    assert detail["resolved"] is True
    assert detail["outcome"] == 1


def test_resolve_writes_leaderboard_row(client, resolved_qid):
    detail = client.get(f"/api/questions/{resolved_qid}").json()
    rows = client.get("/api/leaderboard").json()
    row = next(r for r in rows if r["category"] == detail["category"])
    assert row["n_resolved"] >= 1  # seed corpus + this freshly resolved question


def test_resolved_question_leaves_feed_and_brief(client, resolved_qid):
    assert resolved_qid not in [c["question_id"] for c in client.get("/api/feed").json()]
    assert resolved_qid not in [b["question_id"] for b in client.get("/api/brief?count=20").json()]


def test_double_resolve_conflicts(client, resolved_qid):
    resp = client.post(f"/api/questions/{resolved_qid}/resolve", json={"outcome": False})
    assert resp.status_code == 409


def test_refresh_frozen_after_resolution(client, resolved_qid):
    resp = client.post(f"/api/questions/{resolved_qid}/refresh")
    assert resp.status_code == 409


def test_evidence_frozen_after_resolution(client, resolved_qid):
    body = {
        "source": "late news",
        "summary": "A signal arriving after settlement.",
        "sentiment": "positive",
        "impact": 0.5,
    }
    assert client.post(f"/api/questions/{resolved_qid}/evidence", json=body).status_code == 409


def test_questions_resolved_filter(client, resolved_qid):
    resolved_ids = {q["id"] for q in client.get("/api/questions?resolved=true").json()}
    live_ids = {q["id"] for q in client.get("/api/questions?resolved=false").json()}
    assert resolved_qid in resolved_ids
    assert resolved_qid not in live_ids
    assert resolved_ids.isdisjoint(live_ids)


def test_predictions_track_record_includes_resolution(client, resolved_qid):
    rows = client.get("/api/leaderboard/predictions").json()
    mine = [r for r in rows if r["question_id"] == resolved_qid]
    assert len(mine) == 1
    assert mine[0]["outcome"] == 1
    assert mine[0]["resolved_at"].endswith("Z")


def test_resolved_share_card_carries_stamp(client, resolved_qid):
    svg = client.get(f"/api/cards/{resolved_qid}.svg").text
    assert "RESOLVED YES" in svg
