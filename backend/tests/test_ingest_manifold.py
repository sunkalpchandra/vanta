"""Manifold ingest: corpus + active normalizers and the settlement mapping.

Fixture dicts are real /v0/markets rows (sampled live 2026-08-10), trimmed to
the fields the normalizers read. No test touches the network — the two
`fetch_markets` checks stub the shared HTTP getter.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.ingest.manifold as manifold
from app.db import SessionLocal
from app.ingest.manifold import (
    SOURCE,
    fetch_markets,
    normalize,
    normalize_active,
    resolution_of,
)
from app.ingest.polymarket import upsert_events
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent

# Binary, resolved YES.
MANIFOLD_YES = {
    "id": "CRySyQn8Pc",
    "question": "Will i vape in the next 1 hour",
    "outcomeType": "BINARY",
    "probability": 0.5901639344262298,
    "volume": 127.04412343139049,
    "closeTime": 1786388340000,
    "isResolved": True,
    "resolution": "YES",
    "url": "https://manifold.markets/RickyOYZ/will-i-vape-in-the-next-1-hour",
    "slug": "will-i-vape-in-the-next-1-hour",
}

# Binary, resolved NO.
MANIFOLD_NO = {
    "id": "c9PIQPc0SL",
    "question": "Will three suns rise tomorrow? (Apocalypse hedging)",
    "outcomeType": "BINARY",
    "probability": 0.010000000000000005,
    "volume": 3191.5439616602584,
    "closeTime": 1786388400000,
    "isResolved": True,
    "resolution": "NO",
    "url": "https://manifold.markets/bobalobascrob/will-three-suns-rise-tomorrow-apoca",
    "slug": "will-three-suns-rise-tomorrow-apoca",
}

# Binary, still open — no resolution yet.
MANIFOLD_UNRESOLVED = {
    "id": "ROUQsygPR0",
    "question": "Will Bitcoin be above $65k on August 18?",
    "outcomeType": "BINARY",
    "probability": 0.31,
    "volume": 154.373583582768,
    "closeTime": 1787097540000,
    "isResolved": False,
    "resolution": None,
    "url": "https://manifold.markets/RickyOYZ/will-bitcoin-be-above-65k-on-august",
    "slug": "will-bitcoin-be-above-65k-on-august",
}

# Binary, resolved to the ambiguous probabilistic MKT outcome.
MANIFOLD_MKT = {
    "id": "qA9sZOASUN",
    "question": "Free Lottery (black hole in universe)",
    "outcomeType": "BINARY",
    "probability": 0.6942825440832169,
    "volume": 299.00000000003325,
    "closeTime": 1785986520000,
    "isResolved": True,
    "resolution": "MKT",
    "url": "https://manifold.markets/ttoe/free-lottery-anthropic-dzRt09nLOh",
    "slug": "free-lottery-anthropic-dzRt09nLOh",
}

# Voided market — CANCEL is dropped from the corpus entirely.
MANIFOLD_CANCEL = {
    "id": "UcpulgPzUP",
    "question": "Will Bitcoin be higher at close on Friday? (HIGH LIQUIDITY)",
    "outcomeType": "BINARY",
    "probability": 0.5584915798625553,
    "volume": 562.3578243699061,
    "closeTime": 1786346210733,
    "isResolved": True,
    "resolution": "CANCEL",
    "url": "https://manifold.markets/bigyahu/will-bitcoin-be-higher-at-close-on",
    "slug": "will-bitcoin-be-higher-at-close-on",
}

# A non-binary multiple-choice market — rejected by both normalizers.
MANIFOLD_MULTI = {
    "id": "gg2Q8QSApA",
    "question": "who will win the premier league 26/27 season",
    "outcomeType": "MULTIPLE_CHOICE",
    "probability": None,
    "volume": 13.333333333333334,
    "closeTime": 1811807940000,
    "isResolved": False,
    "resolution": None,
    "url": "https://manifold.markets/MisoPhilipslembrechts/who-will-win-the-premier-league-262",
    "slug": "who-will-win-the-premier-league-262",
}


def _ms_from_now(**delta) -> int:
    return int((datetime.now(UTC) + timedelta(**delta)).timestamp() * 1000)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # ensures tables exist before direct DB writes
        yield c


# --------------------------------------------------------------- corpus normalize


def test_normalize_yes_winner():
    row = normalize(MANIFOLD_YES)
    assert row is not None
    assert row["source"] == SOURCE
    assert row["source_id"] == "CRySyQn8Pc"
    assert row["outcome"] == 1
    assert row["category"] == "other"
    assert row["final_price"] == pytest.approx(0.5901639344262298)
    assert row["volume_usd"] == pytest.approx(127.04412343139049)
    # closeTime is epoch ms -> tz-aware UTC.
    assert row["close_time"] == datetime(2026, 8, 10, 18, 59, tzinfo=UTC)
    assert row["close_time"].utcoffset() == timedelta(0)
    assert row["raw"] == {"url": MANIFOLD_YES["url"], "slug": "will-i-vape-in-the-next-1-hour"}


def test_normalize_no_winner():
    row = normalize(MANIFOLD_NO)
    assert row is not None
    assert row["outcome"] == 0
    assert row["final_price"] == pytest.approx(0.010000000000000005)


def test_normalize_unresolved_keeps_row_without_outcome():
    row = normalize(MANIFOLD_UNRESOLVED)
    assert row is not None
    assert row["outcome"] is None
    assert row["final_price"] == pytest.approx(0.31)  # the current price is still a signal


def test_normalize_mkt_keeps_row_without_outcome():
    # The ambiguous probabilistic outcome resolves nothing, but the row stays.
    row = normalize(MANIFOLD_MKT)
    assert row is not None
    assert row["outcome"] is None


def test_normalize_rejects_cancel_entirely():
    # A voided market carries no backtest signal — dropped, not kept NULL.
    assert normalize(MANIFOLD_CANCEL) is None


def test_normalize_rejects_multiple_choice():
    assert normalize(MANIFOLD_MULTI) is None


def test_normalize_rejects_blank_and_missing_id():
    assert normalize({**MANIFOLD_YES, "question": "   "}) is None
    assert normalize({**MANIFOLD_YES, "id": ""}) is None
    # Non-binary shapes are all rejected regardless of resolution.
    for otype in ("MULTI_NUMERIC", "POLL", "DATE", "PSEUDO_NUMERIC", "PERP"):
        assert normalize({**MANIFOLD_YES, "outcomeType": otype}) is None


# --------------------------------------------------------------- active normalize


def test_normalize_active_accepts_open_in_band_future_close():
    row = normalize_active({**MANIFOLD_UNRESOLVED, "closeTime": _ms_from_now(days=30)})
    assert row is not None
    assert row["source"] == SOURCE
    assert row["source_id"] == "ROUQsygPR0"
    assert row["category"] == "other"
    assert row["yes_price"] == pytest.approx(0.31)
    assert row["closed"] is False
    assert row["outcome"] is None
    assert row["raw"]["slug"] == "will-bitcoin-be-above-65k-on-august"


def test_normalize_active_band_filtering():
    base = {**MANIFOLD_UNRESOLVED, "closeTime": _ms_from_now(days=30)}
    inside = normalize_active({**base, "probability": 0.5})
    assert inside is not None and inside["yes_price"] == pytest.approx(0.5)
    # Strictly inside (0.01, 0.99): the rails and beyond are near-settled junk.
    assert normalize_active({**base, "probability": 0.005}) is None
    assert normalize_active({**base, "probability": 0.995}) is None
    assert normalize_active({**base, "probability": 0.01}) is None
    assert normalize_active({**base, "probability": 0.99}) is None
    assert normalize_active({**base, "probability": None}) is None


def test_normalize_active_requires_future_close():
    assert normalize_active({**MANIFOLD_UNRESOLVED, "closeTime": _ms_from_now(days=1)}) is not None
    assert normalize_active({**MANIFOLD_UNRESOLVED, "closeTime": _ms_from_now(days=-1)}) is None
    assert normalize_active({**MANIFOLD_UNRESOLVED, "closeTime": None}) is None


def test_normalize_active_rejects_resolved_and_nonbinary():
    future = _ms_from_now(days=30)
    # Resolved markets never belong on the tradable surface.
    assert normalize_active({**MANIFOLD_YES, "closeTime": future}) is None
    assert normalize_active({**MANIFOLD_MULTI, "closeTime": future}) is None
    # A one-word "question" is a stub, not a market.
    assert normalize_active({**MANIFOLD_UNRESOLVED, "closeTime": future, "question": "Bitcoin?"}) is None


# --------------------------------------------------------------- resolution_of


def test_resolution_of_mapping():
    assert resolution_of({"resolution": "YES"}) == 1
    assert resolution_of({"resolution": "NO"}) == 0
    assert resolution_of({"resolution": "MKT"}) is None
    assert resolution_of({"resolution": "CANCEL"}) is None
    assert resolution_of({"resolution": None}) is None
    assert resolution_of({}) is None
    assert resolution_of(None) is None


# --------------------------------------------------------------- fetch (stubbed)


def test_fetch_markets_passes_cursor_and_returns_rows(monkeypatch):
    calls = []

    def fake_get_json(url, params):
        calls.append((url, dict(params)))
        return [MANIFOLD_YES, MANIFOLD_NO]

    monkeypatch.setattr(manifold, "_get_json", fake_get_json)
    rows = fetch_markets(before="CRySyQn8Pc", limit=250)
    assert [r["id"] for r in rows] == ["CRySyQn8Pc", "c9PIQPc0SL"]
    assert calls == [(manifold.MARKETS_URL, {"limit": 250, "before": "CRySyQn8Pc"})]


def test_fetch_markets_omits_cursor_when_none(monkeypatch):
    captured = {}

    def fake_get_json(url, params):
        captured.update(params)
        return []

    monkeypatch.setattr(manifold, "_get_json", fake_get_json)
    assert fetch_markets() == []
    assert "before" not in captured  # first page carries no cursor


# --------------------------------------------------- corpus upsert reuse (DB)


def test_corpus_upsert_is_idempotent(client):
    # Scope to a unique source_id so this tolerates the shared suite DB.
    row = {**normalize(MANIFOLD_YES), "source_id": "test-w7-manifold-yes"}
    with SessionLocal() as db:
        kept, skipped = upsert_events(db, [row])
        db.commit()
        assert (kept, skipped) == (1, 0)
        kept, skipped = upsert_events(db, [row])
        db.commit()
        assert (kept, skipped) == (0, 1)
        stored = db.scalars(
            select(MarketEvent).where(
                MarketEvent.source == SOURCE, MarketEvent.source_id == "test-w7-manifold-yes"
            )
        ).all()
    assert len(stored) == 1
    assert stored[0].outcome == 1
    assert stored[0].raw["slug"] == "will-i-vape-in-the-next-1-hour"
