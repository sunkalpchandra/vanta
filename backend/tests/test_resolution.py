import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test_resolution.db"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402


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
