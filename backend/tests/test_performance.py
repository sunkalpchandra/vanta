"""Performance regression guards: query counts and HTTP behaviors that keep
the hot paths flat as the question base grows."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.db import engine
from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def count_statements(callable_):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        callable_()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return statements


def test_feed_is_constant_query_count(client):
    """Regression: the feed used to run one query per live question."""
    statements = count_statements(lambda: client.get("/api/feed"))
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 2, selects


def test_movers_is_constant_query_count(client):
    statements = count_statements(lambda: client.get("/api/feed/movers"))
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 3, selects


def test_sparklines_single_payload(client):
    series = client.get("/api/feed/sparklines").json()
    feed_ids = {c["question_id"] for c in client.get("/api/feed").json()}
    assert feed_ids <= {int(k) for k in series}
    any_series = next(iter(series.values()))
    assert len(any_series) >= 2
    assert all(0 <= p <= 1 for p in any_series)


def test_sparklines_query_count(client):
    statements = count_statements(lambda: client.get("/api/feed/sparklines"))
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) <= 2, selects


def test_cache_headers_on_read_endpoints(client):
    assert "max-age=30" in client.get("/api/feed").headers["cache-control"]
    assert "max-age=300" in client.get("/api/categories").headers["cache-control"]
    assert "cache-control" not in client.get("/api/questions").headers


def test_timing_header_present(client):
    assert float(client.get("/api/stats").headers["x-response-time-ms"]) >= 0
