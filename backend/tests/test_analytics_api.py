from collections import Counter

import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_movers_ranked_by_absolute_delta(client):
    movers = client.get("/api/feed/movers?days=3&limit=5").json()
    assert movers, "seeded questions have 30-day history, so movers must exist"
    deltas = [abs(m["delta"]) for m in movers]
    assert deltas == sorted(deltas, reverse=True)
    for m in movers:
        assert m["delta"] == pytest.approx(m["current"] - m["previous"], abs=1e-3)
        assert m["window_days"] == 3


def test_movers_window_validation(client):
    assert client.get("/api/feed/movers?days=0").status_code == 422


def test_movers_exclude_stale_questions(client):
    """Regression: a question whose forecasts all predate the window used to
    appear as a zero-delta 'mover' (previous row == latest row)."""
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import Forecast

    created = client.post(
        "/api/questions",
        json={"question": "Will this stale movers regression probe resolve YES?", "category": "finance"},
    ).json()
    qid = created["id"]
    with SessionLocal() as db:
        for forecast in db.query(Forecast).filter(Forecast.question_id == qid).all():
            forecast.timestamp = forecast.timestamp - timedelta(days=20)
        db.commit()
    movers = client.get("/api/feed/movers?days=3&limit=20").json()
    assert qid not in [m["question_id"] for m in movers]


def test_brief_ranks_monotonic_in_edge(client):
    """Regression: the diversity backfill used to append a skipped high-edge
    pair after lower-edge picks without re-sorting."""
    brief = client.get("/api/brief?count=7").json()
    edges = [abs(b["edge"]) for b in brief]
    assert edges == sorted(edges, reverse=True)


def test_stats_include_log_scores_and_murphy(client):
    s = client.get("/api/stats").json()
    assert s["vanta_log_score"] > 0
    assert s["market_log_score"] > 0
    assert 0 <= s["vanta_reliability"] <= 1
    assert 0 <= s["vanta_resolution"] <= 0.25 + 1e-9
    assert 0 <= s["outcome_uncertainty"] <= 0.25


def test_question_search(client):
    hits = client.get("/api/questions?q=NVIDIA").json()
    assert hits
    assert all("nvidia" in h["question"].lower() for h in hits)
    assert client.get("/api/questions?q=zzzzunmatchable").json() == []


def test_question_pagination(client):
    full = client.get("/api/questions").json()
    page = client.get("/api/questions?limit=3&offset=2").json()
    assert len(page) == 3
    assert [p["id"] for p in page] == [q["id"] for q in full[2:5]]


def test_analogs_endpoint_mirrors_quant_report(client):
    qid = client.get("/api/questions").json()[-1]["id"]
    payload = client.get(f"/api/questions/{qid}/analogs").json()
    assert "analogs" in payload and "hit_rate" in payload
    for analog in payload["analogs"]:
        assert {"text", "similarity", "outcome"} <= set(analog)


def test_brief_category_diversity(client):
    brief = client.get("/api/brief?count=6").json()
    counts = Counter(item["category"] for item in brief)
    assert counts and max(counts.values()) <= 2


def test_health_reports_db(client):
    body = client.get("/api/health").json()
    assert body["db"] == "ok"
    assert body["status"] == "ok"
