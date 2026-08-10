import pytest
from fastapi.testclient import TestClient

from app.main import _rate_buckets, app  # DB binding happens in conftest.py


@pytest.fixture()
def limited_client():
    app.state.rate_limit_per_minute = 3
    _rate_buckets.clear()
    with TestClient(app) as c:
        yield c
    app.state.rate_limit_per_minute = None
    _rate_buckets.clear()


def test_mutations_rate_limited(limited_client):
    body = {"question": "Will the rate limiter regression probe fire correctly today?", "category": "science"}
    codes = []
    for _ in range(4):
        codes.append(limited_client.post("/api/discover/watchlist", json=body).status_code)
    assert codes[-1] == 429
    resp = limited_client.post("/api/discover/watchlist", json=body)
    assert resp.headers["retry-after"] == "60"


def test_reads_never_rate_limited(limited_client):
    for _ in range(10):
        assert limited_client.get("/api/stats").status_code == 200
