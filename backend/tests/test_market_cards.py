"""Shareable market-card SVG endpoint (/api/market-cards/{event_id}.svg).

Shares the suite SQLite (conftest binds it before app import). Fixture rows are
scoped to a unique source ('test-w10-market-cards') so the global corpus other
modules write into can't perturb these assertions.

main.py wires this router in the integration step (a shared file). Until then,
mount it here — guarded so it's a no-op once main.py includes it.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent
from app.routers import market_cards

if not any(getattr(r, "path", "").startswith("/api/market-cards") for r in app.router.routes):
    app.include_router(market_cards.router)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(
    *,
    question: str = "Will the market-card probe resolve YES?",
    source: str = "polymarket",
    yes_price: float | None = 0.62,
    volume: float = 1234.0,
    outcome: int | None = None,
    category: str = "technology",
) -> int:
    with SessionLocal() as db:
        ev = MarketEvent(
            source=source,
            source_id=f"w10mc-{uuid.uuid4().hex}",
            question=question,
            category=category,
            active=outcome is None,
            outcome=outcome,
            yes_price=yes_price,
            volume_usd=volume,
        )
        db.add(ev)
        db.commit()
        return ev.id


def test_card_renders_valid_svg_with_escaped_question_and_price(client):
    event_id = _make_event(question="Will A & B ship by 2030?", yes_price=0.62, volume=1234.0)
    resp = client.get(f"/api/market-cards/{event_id}.svg")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "max-age" in resp.headers.get("cache-control", "")  # cacheable

    body = resp.text
    assert body.lstrip().startswith("<svg")
    assert body.rstrip().endswith("</svg>")
    # The ampersand is XML-escaped, never emitted raw.
    assert "Will A &amp; B ship by 2030?" in body
    assert " & " not in body
    # Current YES price rendered big; NO is its complement; volume is compact.
    assert "62%" in body  # YES
    assert "38%" in body  # NO = 1 - 0.62
    assert "$1.2K" in body  # volume
    assert "POLYMARKET" in body  # source badge


def test_card_404_for_unknown_event(client):
    resp = client.get("/api/market-cards/999999999.svg")
    assert resp.status_code == 404


def test_card_shows_resolved_yes_stamp(client):
    event_id = _make_event(yes_price=0.9, outcome=1)
    body = client.get(f"/api/market-cards/{event_id}.svg").text
    assert "RESOLVED YES" in body
    assert "RESOLVED NO" not in body


def test_card_shows_resolved_no_stamp(client):
    # outcome=0 is NO — must not be swallowed by a truthiness check.
    event_id = _make_event(yes_price=0.1, outcome=0)
    body = client.get(f"/api/market-cards/{event_id}.svg").text
    assert "RESOLVED NO" in body
    assert "RESOLVED YES" not in body


def test_card_tolerates_missing_price(client):
    event_id = _make_event(yes_price=None, volume=0.0)
    body = client.get(f"/api/market-cards/{event_id}.svg").text
    assert body.lstrip().startswith("<svg")
    assert "—" in body  # em-dash placeholder, never "None%" or "nan%"
    assert "None" not in body


def test_card_carries_play_money_disclaimer(client):
    event_id = _make_event()
    body = client.get(f"/api/market-cards/{event_id}.svg").text
    assert "play money · paper trading · real market prices" in body
