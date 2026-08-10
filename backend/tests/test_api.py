import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Isolated DB per test session, configured before the app module is imported.
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # context manager triggers lifespan (tables + seed)
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_questions_seeded(client):
    questions = client.get("/api/questions").json()
    assert len(questions) >= 10
    assert {"question", "category", "market_probability"} <= set(questions[0])


def test_question_detail_has_forecast_and_debate(client):
    qid = client.get("/api/questions").json()[0]["id"]
    detail = client.get(f"/api/questions/{qid}").json()
    assert detail["latest_forecast"] is not None
    assert 0 < detail["latest_forecast"]["probability"] < 1
    agents = {r["agent"] for r in detail["agent_reports"]}
    assert {"research", "quant", "market", "sentiment", "historian", "skeptic", "synthesis"} == agents


def test_feed_ranked_by_absolute_edge(client):
    feed = client.get("/api/feed").json()
    assert feed
    edges = [abs(card["edge"]) for card in feed]
    assert edges == sorted(edges, reverse=True)


def test_history_returns_series(client):
    qid = client.get("/api/questions").json()[0]["id"]
    history = client.get(f"/api/questions/{qid}/history").json()
    assert len(history) >= 30


def test_leaderboard_has_categories(client):
    rows = client.get("/api/leaderboard").json()
    assert len(rows) >= 4
    for row in rows:
        assert 0 <= row["vanta_accuracy"] <= 1
        assert 0 <= row["vanta_brier"] <= 1


def test_morning_brief(client):
    brief = client.get("/api/brief").json()
    assert len(brief) == 5
    assert brief[0]["rank"] == 1
    assert abs(brief[0]["edge"]) >= abs(brief[-1]["edge"])


def test_ask_creates_question_and_forecast(client):
    body = {
        "question": "Will AGI be achieved before 2035 according to a major lab?",
        "category": "technology",
        "horizon_days": 365,
    }
    created = client.post("/api/questions", json=body).json()
    assert created["latest_forecast"] is not None
    assert len(created["agent_reports"]) == 7


def test_share_card_svg(client):
    qid = client.get("/api/questions").json()[0]["id"]
    resp = client.get(f"/api/cards/{qid}.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "VANTA" in resp.text


def test_missing_question_404(client):
    assert client.get("/api/questions/99999").status_code == 404


def test_timestamps_are_utc_qualified(client):
    """SQLite drops tzinfo; the API must still emit zone-qualified UTC so JS
    Date() doesn't parse timestamps as local time (regression test)."""
    qid = client.get("/api/questions").json()[0]["id"]
    history = client.get(f"/api/questions/{qid}/history").json()
    assert history[0]["timestamp"].endswith("Z")
    detail = client.get(f"/api/questions/{qid}").json()
    assert detail["created_at"].endswith("Z")
    assert detail["latest_forecast"]["timestamp"].endswith("Z")


def test_brief_count_is_validated(client):
    assert client.get("/api/brief?count=0").status_code == 422
    assert client.get("/api/brief?count=-1").status_code == 422
    assert client.get("/api/brief?count=21").status_code == 422


def test_ask_rejects_unknown_category(client):
    body = {"question": "Will this bogus category be rejected by validation?", "category": "x" * 80}
    assert client.post("/api/questions", json=body).status_code == 422
