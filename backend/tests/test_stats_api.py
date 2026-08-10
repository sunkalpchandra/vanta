import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_stats_shape_and_ranges(client):
    s = client.get("/api/stats").json()
    assert s["n_live_questions"] >= 10
    assert s["n_resolved"] >= 30
    assert 0 <= s["vanta_accuracy"] <= 1
    assert 0 <= s["vanta_brier"] <= 1
    assert s["avg_abs_edge"] >= 0
    assert s["llm_narratives"] is False


def test_categories_cover_seeded_corpus(client):
    cats = client.get("/api/categories").json()
    names = {c["category"] for c in cats}
    assert {"finance", "technology", "politics", "science", "sports", "crypto"} <= names
    finance = next(c for c in cats if c["category"] == "finance")
    assert finance["n_live_questions"] >= 1
    assert finance["n_resolved"] >= 1
    assert 0 < finance["base_rate"] < 1


def test_calibration_bins_sum_to_resolved_count(client):
    stats = client.get("/api/stats").json()
    bins = client.get("/api/leaderboard/calibration").json()
    assert len(bins) == 10
    assert sum(b["vanta_count"] for b in bins) == stats["n_resolved"]
    assert sum(b["market_count"] for b in bins) == stats["n_resolved"]
    populated = [b for b in bins if b["vanta_count"] > 0]
    for b in populated:
        assert 0 <= b["vanta_observed_rate"] <= 1
