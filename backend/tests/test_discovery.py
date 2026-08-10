import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmpdir}/test_discovery.db")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_candidates_preview_has_rationales(client):
    candidates = client.get("/api/discover/candidates").json()
    assert len(candidates) >= 5
    assert all(c["rationale"] for c in candidates)


def test_discovery_creates_forecasted_questions(client):
    before = {q["id"] for q in client.get("/api/questions").json()}
    created = client.post("/api/discover?count=2").json()
    assert len(created) == 2
    for item in created:
        assert item["question"]["id"] not in before
        detail = client.get(f"/api/questions/{item['question']['id']}").json()
        assert detail["latest_forecast"] is not None
        assert len(detail["agent_reports"]) == 7


def test_discovery_never_recreates_covered_questions(client):
    first_texts = {i["question"]["question"] for i in client.post("/api/discover?count=2").json()}
    second_texts = {i["question"]["question"] for i in client.post("/api/discover?count=2").json()}
    assert first_texts.isdisjoint(second_texts)


def test_discovery_exhausts_gracefully(client):
    for _ in range(6):
        client.post("/api/discover?count=5")
    assert client.post("/api/discover?count=5").json() == []
    assert client.get("/api/discover/candidates").json() == []
