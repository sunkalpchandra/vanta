"""Settled-markets resolution archive API.

Shares the suite SQLite (conftest binds it before app import). Fixture rows are
scoped to a unique source ('test-w10-archive') and a unique category
('test-w10-archive') so other modules' resolved events and the demo seed never
collide with the category-filtered assertions. The unscoped (all-category)
assertions use invariants, never absolute totals — the whole corpus resolves
into this endpoint.

Until main.py wires the market-archive router (a shared file, handled in the
integration step), mount it here — a guarded no-op once main.py includes it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.routers import market_archive

_ARCHIVE_PATH = "/api/market-archive"
if not any(getattr(r, "path", None) == _ARCHIVE_PATH for r in app.router.routes):
    app.include_router(market_archive.router)

SOURCE = "test-w10-archive"
CATEGORY = "test-w10-archive"  # unique category isolates our rows from the corpus


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(
    *,
    category: str = CATEGORY,
    outcome: int | None = None,
    final_price: float | None = None,
    close_days_ago: float = 1.0,
    active: bool = False,
    volume: float = 0.0,
) -> int:
    with SessionLocal() as db:
        ev = MarketEvent(
            source=SOURCE,
            source_id=f"w10a-{uuid.uuid4().hex}",
            question=f"Will archive probe {uuid.uuid4().hex[:6]} resolve YES?",
            category=category,
            active=active,
            outcome=outcome,
            final_price=final_price,
            volume_usd=volume,
            close_time=datetime.now(UTC) - timedelta(days=close_days_ago),
        )
        db.add(ev)
        db.commit()
        return ev.id


def test_returns_only_resolved_newest_close_first(client):
    # Two resolved events (different close times) + one still-active event, all
    # in our unique category so the category filter returns exactly these.
    older = _make_event(outcome=1, final_price=0.82, close_days_ago=10)
    newer = _make_event(outcome=0, final_price=0.71, close_days_ago=2)
    active = _make_event(outcome=None, final_price=None, active=True, close_days_ago=1)

    body = client.get(f"/api/market-archive?category={CATEGORY}").json()
    assert body["total"] == 2  # active one excluded (outcome is null)
    ids = [it["event_id"] for it in body["items"]]
    assert ids == [newer, older]  # newest close_time first
    assert active not in ids


def test_item_shape_exposes_final_price_and_outcome(client):
    eid = _make_event(outcome=1, final_price=0.82, close_days_ago=3, volume=1234.5)
    body = client.get(f"/api/market-archive?category={CATEGORY}").json()
    item = next(it for it in body["items"] if it["event_id"] == eid)
    assert set(item) == {
        "event_id",
        "question",
        "category",
        "source",
        "outcome",
        "final_price",
        "close_time",
        "volume_usd",
    }
    assert item["outcome"] == 1
    assert item["final_price"] == pytest.approx(0.82)
    assert item["source"] == SOURCE
    assert item["volume_usd"] == pytest.approx(1234.5)
    assert item["close_time"].endswith("Z")  # zone-qualified UTC


def test_pagination(client):
    # Fresh unique category so total is exactly what we seed here.
    cat = f"{CATEGORY}-page-{uuid.uuid4().hex[:6]}"
    a = _make_event(category=cat, outcome=1, final_price=0.6, close_days_ago=9)
    b = _make_event(category=cat, outcome=0, final_price=0.4, close_days_ago=6)
    c = _make_event(category=cat, outcome=1, final_price=0.9, close_days_ago=3)
    newest_first = [c, b, a]

    page1 = client.get(f"/api/market-archive?category={cat}&limit=2&offset=0").json()
    assert page1["total"] == 3
    assert [it["event_id"] for it in page1["items"]] == newest_first[:2]

    page2 = client.get(f"/api/market-archive?category={cat}&limit=2&offset=2").json()
    assert page2["total"] == 3  # total is the full count, independent of the page
    assert [it["event_id"] for it in page2["items"]] == newest_first[2:]


def test_category_filter_isolates(client):
    cat_a = f"{CATEGORY}-A-{uuid.uuid4().hex[:6]}"
    cat_b = f"{CATEGORY}-B-{uuid.uuid4().hex[:6]}"
    in_a = _make_event(category=cat_a, outcome=1, final_price=0.7)
    in_b = _make_event(category=cat_b, outcome=0, final_price=0.3)

    body_a = client.get(f"/api/market-archive?category={cat_a}").json()
    ids_a = [it["event_id"] for it in body_a["items"]]
    assert in_a in ids_a
    assert in_b not in ids_a
    assert all(it["category"] == cat_a for it in body_a["items"])


def test_unfiltered_returns_only_resolved(client):
    # No category filter: a global aggregate over the whole corpus. Assert the
    # invariant (every row is resolved) rather than an absolute total.
    _make_event(outcome=1, final_price=0.5)
    body = client.get("/api/market-archive?limit=100").json()
    assert body["total"] >= 1
    assert body["items"]  # something has resolved
    assert all(it["outcome"] is not None for it in body["items"])
