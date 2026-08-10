import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


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


def test_feed_limit_caps_and_keeps_top_edges(client):
    full = client.get("/api/feed").json()
    limited = client.get("/api/feed?limit=3").json()
    assert len(limited) == 3
    assert [c["question_id"] for c in limited] == [c["question_id"] for c in full[:3]]


def test_history_returns_series(client):
    # Oldest question = seeded with 30-day backfill (list is newest-first, and
    # other test modules may have minted newer questions with short histories).
    qid = client.get("/api/questions").json()[-1]["id"]
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
    assert 1.0 <= brief[0]["confidence"] <= 10.0


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


def test_evidence_carries_spread_timestamps(client):
    """Seeded evidence arrival dates are spread over past weeks and serialized
    as zone-qualified UTC."""
    detail = client.get(f"/api/questions/{client.get('/api/questions').json()[-1]['id']}").json()
    assert detail["evidence"], "seeded question must have evidence"
    stamps = [e["created_at"] for e in detail["evidence"]]
    assert all(s.endswith("Z") for s in stamps)
    assert len(set(s[:10] for s in stamps)) >= 2  # not all the same day


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
