"""Kalshi ingest: normalizer against real sampled rows, the junk filter that
keeps multivariate combos out of the corpus, leakage-safe price snapshots,
and upsert idempotence. No live network — HTTP goes through MockTransport.

Fixture rows are real /markets responses sampled 2026-08-10, trimmed to the
fields the normalizer reads (rules_* boilerplate and orderbook noise cut).
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db import Base, SessionLocal, engine
from app.ingest.kalshi import (
    SOURCE,
    fetch_candles,
    fetch_markets,
    normalize,
    normalize_category,
    price_at,
    series_ticker_of,
    upsert_event,
)
from app.models import MarketEvent

CLEAN_YES = {
    "ticker": "KXCPIYOY-26MAY-T4.1",
    "event_ticker": "KXCPIYOY-26MAY",
    "title": "Will the rate of CPI inflation be above 4.1% for the year ending in May 2026?",
    "yes_sub_title": "Above 4.1%",
    "result": "yes",
    "status": "finalized",
    "market_type": "binary",
    "close_time": "2026-06-10T12:29:00Z",
    "open_time": "2026-04-27T16:30:00Z",
    "last_price_dollars": "0.7600",
    "volume_fp": "114504.81",
    "strike_type": "greater",
}

CLEAN_NO = {
    "ticker": "KXCPIYOY-26JUN-T4.5",
    "event_ticker": "KXCPIYOY-26JUN",
    "title": "Will the rate of CPI inflation be above 4.5% for the year ending in June 2026?",
    "yes_sub_title": "Above 4.5%",
    "result": "no",
    "status": "finalized",
    "market_type": "binary",
    "close_time": "2026-07-14T12:29:00Z",
    "last_price_dollars": "0.0100",
    "volume_fp": "22205.25",
    "strike_type": "greater",
}

WEATHER_STRIKE = {
    "ticker": "KXHIGHNY-26AUG08-T96",
    "event_ticker": "KXHIGHNY-26AUG08",
    "title": "Will the **high temp in NYC** be >96° on Aug 8, 2026?",
    "yes_sub_title": "97° or above",
    "result": "no",
    "status": "finalized",
    "market_type": "binary",
    "close_time": "2026-08-09T04:59:00Z",
    "last_price_dollars": "0.0100",
    "volume_fp": "1392.91",
    "strike_type": "greater",
}

# The junk that floods recent settled pages: a multivariate cross-category
# combo — comma-joined leg titles, KXMVE ticker, zero volume.
MVE_COMBO = {
    "ticker": "KXMVECROSSCATEGORY-S20267FCACCD6EBE-49E48C04C4C",
    "event_ticker": "KXMVECROSSCATEGORY-S20267FCACCD6EBE",
    "title": "yes Target Price: $65,219.15,yes Target Price: $1,925.78,yes Afghanistan,yes Target Price: $1.0359",
    "yes_sub_title": "yes Target Price: $65,219.15,yes Target Price: $1,925.78,"
    "yes Afghanistan,yes Target Price: $1.0359",
    "result": "no",
    "status": "finalized",
    "market_type": "binary",
    "close_time": "2026-08-10T08:33:42Z",
    "last_price_dollars": "0.0000",
    "volume_fp": "0.00",
    "mve_collection_ticker": "KXMVECROSSCATEGORY-R",
    "strike_type": "custom",
}

ZERO_VOLUME = {
    "ticker": "KXFEAR-25MAR28-XGREED",
    "event_ticker": "KXFEAR-25MAR28",
    "title": "What will the Fear & Greed Index be on Mar 28, 2025?",
    "yes_sub_title": "Extreme Greed",
    "result": "no",
    "status": "finalized",
    "market_type": "binary",
    "close_time": "2025-03-28T20:00:00Z",
    "last_price_dollars": "0.0000",
    "volume_fp": "0.00",
    "strike_type": "custom",
}


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def test_normalize_clean_yes_market():
    event = normalize(CLEAN_YES)
    assert event is not None
    assert event["source"] == SOURCE
    assert event["source_id"] == "KXCPIYOY-26MAY-T4.1"
    assert event["outcome"] == 1
    assert event["final_price"] == pytest.approx(0.76)
    assert event["volume_usd"] == pytest.approx(114504.81)
    assert event["category"] == "finance"
    # Subtitle "Above 4.1%" already appears in the title — no redundant suffix.
    assert event["question"] == CLEAN_YES["title"]
    assert event["close_time"] == datetime(2026, 6, 10, 12, 29, tzinfo=UTC)
    assert event["close_time"].utcoffset() == timedelta(0)  # stored tz-aware UTC
    assert event["raw"]["event_ticker"] == "KXCPIYOY-26MAY"


def test_normalize_clean_no_market():
    event = normalize(CLEAN_NO)
    assert event is not None
    assert event["outcome"] == 0
    assert event["final_price"] == pytest.approx(0.01)


def test_normalize_strips_markdown_and_appends_strike():
    event = normalize(WEATHER_STRIKE)
    assert event is not None
    assert "**" not in event["question"]
    # The subtitle pins down the strike the title alone doesn't state.
    assert event["question"].endswith("(97° or above)")
    assert event["category"] == "science"  # KXHIGHNY — weather series keyword
    assert series_ticker_of(WEATHER_STRIKE) == "KXHIGHNY"


def test_normalize_rejects_mve_combo():
    assert normalize(MVE_COMBO) is None
    # Even without the mve_* fields, the ticker prefix alone must reject it.
    stripped = {k: v for k, v in MVE_COMBO.items() if k != "mve_collection_ticker"}
    assert normalize(stripped) is None


def test_normalize_rejects_zero_volume():
    assert normalize(ZERO_VOLUME) is None


def test_normalize_rejects_unresolved_and_broken_rows():
    unresolved = dict(CLEAN_YES, result="")
    assert normalize(unresolved) is None
    no_title = dict(CLEAN_YES, title="")
    assert normalize(no_title) is None
    non_binary = dict(CLEAN_YES, market_type="scalar")
    assert normalize(non_binary) is None


def test_category_normalization():
    assert normalize_category("Politics", "KXWHATEVERX-26") == "politics"
    assert normalize_category("Climate and Weather", "KXWHATEVERX-26") == "science"
    assert normalize_category("Economics", "KXWHATEVERX-26") == "finance"
    # Explicit event category beats ticker inference.
    assert normalize_category("Sports", "KXBTCD-26AUG10") == "sports"
    # No category on /markets rows — infer from the series ticker.
    assert normalize_category(None, "KXBTCD-26AUG10-T65000") == "crypto"
    assert normalize_category(None, "KXCPIYOY-26JUN-T4.5") == "finance"
    assert normalize_category(None, "KXUKRAINE-26-CEASE") == "politics"
    assert normalize_category(None, "KXWHATEVERX-26") == "other"


def test_price_at_is_leakage_safe():
    close = datetime(2026, 7, 14, 12, 29, tzinfo=UTC)

    def days_ago(n: float) -> int:
        return int((close - timedelta(days=n)).timestamp())

    history = [
        {"t": days_ago(10), "p": 0.10},
        {"t": days_ago(8), "p": 0.20},
        {"t": days_ago(6), "p": 0.90},  # after the 7d cutoff — must not leak
        {"t": days_ago(1), "p": 0.99},
    ]
    assert price_at(history, close, 7) == pytest.approx(0.20)
    assert price_at(history, close, 30) is None  # no history that early
    assert price_at([], close, 7) is None
    # SQLite round-trips drop tzinfo — naive close_time means UTC, same answer.
    assert price_at(history, close.replace(tzinfo=None), 7) == pytest.approx(0.20)


def test_fetch_candles_parses_both_shapes_and_degrades():
    candles = {
        "ticker": "KXCPIYOY-26JUN-T4.5",
        "candlesticks": [
            {"end_period_ts": 1781064000, "price": {"close_dollars": "0.8000"}},
            {"end_period_ts": 1780977600, "price": {"close": 82}},  # legacy cents
            {"end_period_ts": 1781150400, "price": {"close_dollars": None}},  # no trades
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/series/KXCPIYOY/markets/KXCPIYOY-26JUN-T4.5/candlesticks" in str(request.url)
        assert request.url.params["period_interval"] == "1440"
        return httpx.Response(200, json=candles)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        closes = fetch_candles("KXCPIYOY", "KXCPIYOY-26JUN-T4.5", 1780000000, 1782000000, client=client)
    assert closes == [
        {"t": 1780977600, "p": 0.82},  # sorted oldest-first, cents scaled
        {"t": 1781064000, "p": 0.80},
    ]

    def gated(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    with httpx.Client(transport=httpx.MockTransport(gated)) as client:
        assert fetch_candles("KXCPIYOY", "KXCPIYOY-26JUN-T4.5", 0, 1, client=client) == []

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with httpx.Client(transport=httpx.MockTransport(down)) as client:
        assert fetch_candles("KXCPIYOY", "KXCPIYOY-26JUN-T4.5", 0, 1, client=client) == []


def test_fetch_markets_returns_page_and_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "settled"
        assert request.url.params["limit"] == "1000"
        if request.url.params.get("cursor") == "page2":
            return httpx.Response(200, json={"markets": [CLEAN_NO], "cursor": ""})
        return httpx.Response(200, json={"markets": [CLEAN_YES, MVE_COMBO], "cursor": "page2"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        markets, cursor = fetch_markets(client=client)
        assert [m["ticker"] for m in markets] == [CLEAN_YES["ticker"], MVE_COMBO["ticker"]]
        assert cursor == "page2"
        markets, cursor = fetch_markets(cursor, client=client)
        assert [m["ticker"] for m in markets] == [CLEAN_NO["ticker"]]
        assert cursor is None  # empty cursor string means exhausted


def test_upsert_is_idempotent_and_preserves_price_snapshots(db):
    values = normalize(CLEAN_YES)
    row, created = upsert_event(db, values)
    db.commit()
    assert created
    _, created_again = upsert_event(db, normalize(CLEAN_YES))
    db.commit()
    rows = db.query(MarketEvent).filter_by(source=SOURCE, source_id=values["source_id"]).all()
    assert not created_again
    assert len(rows) == 1

    # The slow price pass owns price_7d/30d — re-ingesting must not wipe them.
    rows[0].price_7d = 0.42
    db.commit()
    updated = dict(normalize(CLEAN_YES), volume_usd=999999.0)
    upsert_event(db, updated)
    db.commit()
    refreshed = db.query(MarketEvent).filter_by(source=SOURCE, source_id=values["source_id"]).one()
    assert refreshed.volume_usd == pytest.approx(999999.0)
    assert refreshed.price_7d == pytest.approx(0.42)
