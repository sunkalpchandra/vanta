import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _question_with_evidence(client) -> dict:
    for q in reversed(client.get("/api/questions?resolved=false").json()):
        detail = client.get(f"/api/questions/{q['id']}").json()
        if len(detail["evidence"]) >= 3:
            return detail
    pytest.fail("no live question with evidence")


def test_sensitivity_shape_and_direction(client):
    detail = _question_with_evidence(client)
    items = client.get(f"/api/questions/{detail['id']}/sensitivity").json()["items"]
    assert len(items) == len(detail["evidence"])
    # Sorted by absolute influence.
    deltas = [abs(i["delta"]) for i in items]
    assert deltas == sorted(deltas, reverse=True)
    # Direction sanity: removing a supportive signal shouldn't RAISE the
    # forecast, and vice versa (delta is full - without).
    for item in items:
        if item["sentiment"] == "positive":
            assert item["delta"] >= -1e-9
        elif item["sentiment"] == "negative":
            assert item["delta"] <= 1e-9


def test_sensitivity_empty_for_evidence_free_question(client):
    created = client.post(
        "/api/questions",
        json={"question": "Will this evidence-free sensitivity probe resolve YES?", "category": "science"},
    ).json()
    assert client.get(f"/api/questions/{created['id']}/sensitivity").json()["items"] == []


def test_sensitivity_is_deterministic(client):
    detail = _question_with_evidence(client)
    a = client.get(f"/api/questions/{detail['id']}/sensitivity").json()
    b = client.get(f"/api/questions/{detail['id']}/sensitivity").json()
    assert a == b
