"""Live market sync: active normalizers against real probed rows, the
stateless reconcile (insert -> update -> venue-close -> relist), stale
delisting, and the settlement sweep's settle hook. No live network — HTTP
goes through MockTransport or stubbed fetchers.

Fixture rows are real API responses sampled 2026-08-10 (gamma
/markets?closed=false&active=true and kalshi /markets?status=open), trimmed
to the fields the normalizers read.

Shared suite DB: rows use throwaway sources ("test-sync", "test-stale") or
unique source_ids so other modules' writes never collide; the settlement
sweep test tolerates candidates from other modules by stubbing unknown ids
to "not resolved"."""

import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.db import Base, SessionLocal, engine
from app.ingest import active
from app.ingest.active import (
    deactivate_stale,
    fetch_active_kalshi,
    fetch_active_polymarket,
    normalize_active,
    normalize_active_kalshi,
    resolution_of,
    sync_active,
)
from app.models import MarketEvent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from sync_markets import settlement_sweep  # noqa: E402

# --- Polymarket fixtures (gamma /markets?closed=false&active=true) ----------

PM_IRAN = {
    "id": "665374",
    "question": "Will the U.S. invade Iran before 2027?",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.165", "0.835"]',
    "closed": False,
    "active": True,
    "endDate": "2026-12-31T00:00:00Z",
    "closedTime": None,
    "volumeNum": 57929808.87614796,
    "category": None,
    "slug": "will-the-us-invade-iran-before-2027",
    "clobTokenIds": '["55115078421062885512539156303747803058407616201213034911037320915726138659123", '
    '"1910830010387565971650098373488592514702818137344973088263643820608151819241"]',
    "tags": [{"label": "Military Strikes"}, {"label": "Politics"}, {"label": "Iran"}],
}

# Category falls through to "other" — allowed on the markets surface.
PM_CULTURE = {
    "id": "703258",
    "question": "Will Jesus Christ return before 2027?",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.0205", "0.9795"]',
    "closed": False,
    "active": True,
    "endDate": "2026-12-31T00:00:00Z",
    "volumeNum": 64985000.96862789,
    "category": None,
    "slug": "will-jesus-christ-return-before-2027",
    "clobTokenIds": '["69324317355037271422943965141382095011871956039434394956830818206664869608517", '
    '"51797157743046504218541616681751597845468055908324407922581755135522797852101"]',
    "tags": [{"label": "Culture"}, {"label": "Parent For Derivative"}],
}

# Near-settled junk: YES at 0.0055 is outside the tradable band.
PM_NEAR_SETTLED = {
    "id": "2063134",
    "question": "Will Adanech Abiebie be the next Prime Minister of Ethiopia?",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.0055", "0.9945"]',
    "closed": False,
    "active": True,
    "endDate": "2026-06-01T00:00:00Z",
    "volumeNum": 76722456.729933,
    "category": None,
    "slug": "will-adanech-abiebie-be-the-next-prime-minister-of-ethiopia",
    "clobTokenIds": '["27146956652877944551877724690365745048289675287536243265951843487691050802191"]',
    "tags": [{"label": "Ethiopia"}, {"label": "Elections"}],
}

# --- Kalshi fixtures (/markets?status=open) ---------------------------------

KX_MLB = {
    "ticker": "KXMLBGAME-26AUG131335SEANYY-SEA",
    "event_ticker": "KXMLBGAME-26AUG131335SEANYY",
    "title": "Seattle vs New York Y Winner?",
    "yes_sub_title": "Seattle",
    "result": "",
    "status": "active",
    "market_type": "binary",
    "open_time": "2026-08-10T17:55:00Z",
    "close_time": "2026-08-16T17:35:00Z",
    "last_price_dollars": "0.4700",
    "volume_fp": "15.00",
}

# The intraday micro-strike flood: open->close under 3 hours.
KX_BRENT_MICRO = {
    "ticker": "KXBRENTD-26AUG1017-T88.50",
    "event_ticker": "KXBRENTD-26AUG1017",
    "title": "Will the brent crude oil close price be above 88.50 USD/Bbl on August 10, 2026 at 5:00 PM EDT?",
    "yes_sub_title": "Above $88.50",
    "result": "",
    "status": "active",
    "market_type": "binary",
    "open_time": "2026-08-10T18:11:00Z",
    "close_time": "2026-08-10T21:00:00Z",
    "last_price_dollars": "0.1200",
    "volume_fp": "322.00",
}

# Multivariate combo junk that floods the open feed without mve_filter.
KX_MVE_OPEN = {
    "ticker": "KXMVECROSSCATEGORY-S2026D46917673AC-7390865C460",
    "event_ticker": "KXMVECROSSCATEGORY-S2026D46917673AC",
    "title": "yes Sevilla,yes Celta Vigo,yes Villarreal,yes Vancouver",
    "yes_sub_title": "yes Sevilla,yes Celta Vigo,yes Villarreal,yes Vancouver",
    "result": "",
    "status": "active",
    "market_type": "binary",
    "open_time": "2026-08-10T18:14:44Z",
    "close_time": "2026-08-19T08:30:00Z",
    "last_price_dollars": "0.0000",
    "volume_fp": "0.00",
    "mve_collection_ticker": "KXMVECROSSCATEGORY-R",
}


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# ------------------------------------------------------ normalize_active (PM)


def test_normalize_active_accepts_clean_market():
    row = normalize_active(PM_IRAN)
    assert row is not None
    assert row["source"] == "polymarket"
    assert row["source_id"] == "665374"
    assert row["yes_price"] == pytest.approx(0.165)
    assert row["category"] == "politics"  # from tags — gamma category is null
    assert row["volume_usd"] == pytest.approx(57929808.87614796)
    assert row["close_time"] == datetime(2026, 12, 31, tzinfo=UTC)
    assert row["close_time"].utcoffset() == timedelta(0)
    assert row["closed"] is False and row["outcome"] is None
    # Raw is trimmed to exactly what later stages need.
    assert set(row["raw"]) == {"slug", "clobTokenIds", "endDate"}
    assert len(row["raw"]["clobTokenIds"]) == 2


def test_normalize_active_allows_other_category():
    row = normalize_active(PM_CULTURE)
    assert row is not None
    assert row["category"] == "other"  # markets surface isn't the curated feed
    assert row["yes_price"] == pytest.approx(0.0205)


def test_normalize_active_rejects_junk():
    # Near-settled: price outside [0.01, 0.99].
    assert normalize_active(PM_NEAR_SETTLED) is None
    assert normalize_active(dict(PM_IRAN, outcomePrices='["0.995", "0.005"]')) is None
    # Settled-at-the-rail closed rows are junk too, not tradable listings.
    assert normalize_active(dict(PM_IRAN, closed=True, outcomePrices='["1", "0"]')) is None
    # Non-binary outcomes, short questions, missing/broken prices.
    assert normalize_active(dict(PM_IRAN, outcomes='["Up", "Down"]')) is None
    assert normalize_active(dict(PM_IRAN, question="Iran?")) is None
    assert normalize_active(dict(PM_IRAN, outcomePrices="[]")) is None
    assert normalize_active(dict(PM_IRAN, outcomePrices='["abc", "def"]')) is None
    assert normalize_active(dict(PM_IRAN, id="")) is None


def test_normalize_active_boundary_prices_are_tradable():
    assert normalize_active(dict(PM_IRAN, outcomePrices='["0.01", "0.99"]')) is not None
    assert normalize_active(dict(PM_IRAN, outcomePrices='["0.99", "0.01"]')) is not None


# -------------------------------------------------- normalize_active (Kalshi)


def test_normalize_active_kalshi_accepts_multi_day_market():
    row = normalize_active_kalshi(KX_MLB)
    assert row is not None
    assert row["source"] == "kalshi"
    assert row["source_id"] == "KXMLBGAME-26AUG131335SEANYY-SEA"
    assert row["yes_price"] == pytest.approx(0.47)
    assert row["category"] == "sports"  # MLB series-ticker keyword
    # Subtitle "Seattle" already appears in the title — no redundant suffix.
    assert row["question"] == "Seattle vs New York Y Winner?"
    assert row["close_time"] == datetime(2026, 8, 16, 17, 35, tzinfo=UTC)
    assert row["closed"] is False and row["outcome"] is None


def test_normalize_active_kalshi_rejects_micro_markets_and_junk():
    # Lifetime under 3 days — the intraday strike flood.
    assert normalize_active_kalshi(KX_BRENT_MICRO) is None
    # Multivariate combos, by mve field and by ticker prefix alone.
    assert normalize_active_kalshi(KX_MVE_OPEN) is None
    stripped = {k: v for k, v in KX_MVE_OPEN.items() if k != "mve_collection_ticker"}
    assert normalize_active_kalshi(stripped) is None
    # Price at/outside the (0.01, 0.99) band, or absent entirely.
    assert normalize_active_kalshi(dict(KX_MLB, last_price_dollars="0.0000")) is None
    assert normalize_active_kalshi(dict(KX_MLB, last_price_dollars="0.9900")) is None
    assert normalize_active_kalshi(dict(KX_MLB, last_price_dollars="0.0100")) is None
    assert normalize_active_kalshi({**KX_MLB, "last_price_dollars": None}) is None
    # Broken rows: no times, short titles, non-binary.
    assert normalize_active_kalshi({**KX_MLB, "open_time": None}) is None
    assert normalize_active_kalshi(dict(KX_MLB, title="Winner?")) is None
    assert normalize_active_kalshi(dict(KX_MLB, market_type="scalar")) is None


def test_normalize_active_kalshi_carries_result_marker():
    settled = dict(KX_MLB, result="yes", status="finalized", last_price_dollars="0.5000")
    row = normalize_active_kalshi(settled)
    assert row is not None
    assert row["closed"] is True
    assert row["outcome"] == 1


# ------------------------------------------------------------------- fetchers


def test_fetch_active_polymarket_handles_offset_cap(monkeypatch):
    calls = {}

    def fake_get_json(url, params):
        calls.update(params)
        if params["offset"] >= 2000:
            request = httpx.Request("GET", url)
            response = httpx.Response(
                422, text='{"error":"offset too large, use /markets/keyset"}', request=request
            )
            raise httpx.HTTPStatusError("422", request=request, response=response)
        return [PM_IRAN]

    monkeypatch.setattr(active, "_get_json", fake_get_json)
    assert fetch_active_polymarket(0, 100) == [PM_IRAN]
    assert calls["closed"] == "false" and calls["active"] == "true"
    # The depth cap means "you already have the top markets", not an error.
    assert fetch_active_polymarket(2900, 100) == []


def test_fetch_active_kalshi_filters_and_pages():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["status"] == "open"
        assert request.url.params["mve_filter"] == "exclude"  # 60k rows -> 312 real without it
        if request.url.params.get("cursor") == "page2":
            return httpx.Response(200, json={"markets": [], "cursor": ""})
        return httpx.Response(
            200, json={"markets": [KX_MLB, KX_BRENT_MICRO, KX_MVE_OPEN], "cursor": "page2"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, cursor = fetch_active_kalshi(client=client)
        assert [row["source_id"] for row in rows] == [KX_MLB["ticker"]]  # junk filtered out
        assert cursor == "page2"
        rows, cursor = fetch_active_kalshi(cursor, client=client)
        assert rows == [] and cursor is None  # empty cursor string means exhausted


# ---------------------------------------------------------------- sync_active


def _as_test_rows(*markets, source="test-sync"):
    rows = []
    for market in markets:
        normalized = normalize_active(market) if "outcomePrices" in market else normalize_active_kalshi(market)
        assert normalized is not None
        rows.append(dict(normalized, source=source))
    return rows


def test_sync_active_insert_then_update(db):
    rows = _as_test_rows(PM_IRAN, KX_MLB)
    counts = sync_active(db, rows, "test-sync")
    db.commit()
    assert counts == {"added": 2, "updated": 0, "closed": 0}

    event = db.query(MarketEvent).filter_by(source="test-sync", source_id="665374").one()
    assert event.active is True
    assert event.yes_price == pytest.approx(0.165)
    assert event.last_synced is not None

    # The slow price pass owns the snapshots — syncing must not wipe them.
    event.price_7d = 0.42
    db.commit()

    updated = _as_test_rows(dict(PM_IRAN, outcomePrices='["0.30", "0.70"]', volumeNum=60000000.0), KX_MLB)
    counts = sync_active(db, updated, "test-sync")
    db.commit()
    assert counts == {"added": 0, "updated": 2, "closed": 0}
    db.refresh(event)
    assert event.yes_price == pytest.approx(0.30)
    assert event.volume_usd == pytest.approx(60000000.0)
    assert event.price_7d == pytest.approx(0.42)
    assert db.query(MarketEvent).filter_by(source="test-sync").count() == 2


def test_sync_active_venue_close_flips_inactive(db):
    (row,) = _as_test_rows(KX_MLB)
    sync_active(db, [row], "test-sync")
    db.commit()
    closed_row = dict(row, closed=True, outcome=1)
    counts = sync_active(db, [closed_row], "test-sync")
    db.commit()
    assert counts["closed"] == 1
    event = db.query(MarketEvent).filter_by(source="test-sync", source_id=KX_MLB["ticker"]).one()
    assert event.active is False
    assert event.outcome == 1

    # A resolved event never relists, even if the venue feed shows it open.
    sync_active(db, [row], "test-sync")
    db.commit()
    db.refresh(event)
    assert event.active is False
    assert event.outcome == 1  # and the outcome is never overwritten


def test_sync_active_relists_stale_but_open_events(db):
    (row,) = _as_test_rows(PM_CULTURE)
    sync_active(db, [row], "test-sync")
    db.commit()
    event = db.query(MarketEvent).filter_by(source="test-sync", source_id="703258").one()
    event.active = False  # premature stale deactivation
    db.commit()
    sync_active(db, [row], "test-sync")
    db.commit()
    db.refresh(event)
    assert event.active is True  # reappeared in the feed -> tradable again


def test_sync_active_ignores_rows_from_other_sources(db):
    rows = _as_test_rows(PM_IRAN)  # source overridden to test-sync
    counts = sync_active(db, rows, "some-other-source")
    assert counts == {"added": 0, "updated": 0, "closed": 0}


# ----------------------------------------------------------- deactivate_stale


def test_deactivate_stale_flips_only_stale_rows(db):
    now = datetime.now(UTC)
    fresh = MarketEvent(
        source="test-stale", source_id="fresh", question="fresh row", category="other",
        active=True, yes_price=0.5, last_synced=now,
    )
    stale = MarketEvent(
        source="test-stale", source_id="stale", question="stale row", category="other",
        active=True, yes_price=0.5, last_synced=now - timedelta(hours=48),
    )
    never = MarketEvent(
        source="test-stale", source_id="never", question="never synced", category="other",
        active=True, yes_price=0.5, last_synced=None,
    )
    db.add_all([fresh, stale, never])
    db.commit()

    flipped = deactivate_stale(db, "test-stale", older_than_hours=24)
    db.commit()
    assert flipped == 2
    db.refresh(fresh), db.refresh(stale), db.refresh(never)
    assert fresh.active is True
    assert stale.active is False
    assert never.active is False


# -------------------------------------------------------------- resolution_of


def test_resolution_of_reads_venue_rows():
    assert resolution_of("polymarket", {"closed": True, "outcomePrices": '["1", "0"]'}) == 1
    assert resolution_of("polymarket", {"closed": True, "outcomePrices": '["0", "1"]'}) == 0
    assert resolution_of("polymarket", {"closed": False, "outcomePrices": '["0.5", "0.5"]'}) is None
    # ["0","0"] means the resolution never reached the API — not derivable.
    assert resolution_of("polymarket", {"closed": True, "outcomePrices": '["0", "0"]'}) is None
    assert resolution_of("kalshi", {"result": "yes"}) == 1
    assert resolution_of("kalshi", {"result": "no"}) == 0
    assert resolution_of("kalshi", {"result": ""}) is None
    assert resolution_of("kalshi", None) is None
    assert resolution_of("test-sync", None) is None  # row-None short-circuits before source check


# ----------------------------------------------------------- settlement sweep


def test_settlement_sweep_settles_resolved_events(db, monkeypatch):
    now = datetime.now(UTC)
    listed_resolved = MarketEvent(
        source="polymarket", source_id="test-sweep-pm-1", question="sweep: listed, close passed",
        category="other", active=True, yes_price=0.6, last_synced=now,
        close_time=now - timedelta(hours=2),
    )
    delisted_resolved = MarketEvent(
        source="kalshi", source_id="TEST-SWEEP-KX-1", question="sweep: recently delisted",
        category="other", active=False, yes_price=0.2, last_synced=now - timedelta(hours=6),
    )
    still_open = MarketEvent(
        source="polymarket", source_id="test-sweep-pm-2", question="sweep: close in the future",
        category="other", active=True, yes_price=0.5, last_synced=now,
        close_time=now + timedelta(days=30),
    )
    long_gone = MarketEvent(
        source="kalshi", source_id="TEST-SWEEP-KX-2", question="sweep: delisted ages ago",
        category="other", active=False, yes_price=0.5, last_synced=now - timedelta(days=10),
    )
    db.add_all([listed_resolved, delisted_resolved, still_open, long_gone])
    db.commit()

    settled_calls = []
    trading = types.ModuleType("app.trading")

    def _settle_event(session, event):
        settled_calls.append(event)
        return 1

    trading.settle_event = _settle_event
    trading.settle_resolved = lambda session: 0  # position-driven backstop (no-op here)
    monkeypatch.setitem(sys.modules, "app.trading", trading)

    probed = []
    venue_rows = {
        "test-sweep-pm-1": {"closed": True, "outcomePrices": '["1", "0"]'},
        "TEST-SWEEP-KX-1": {"result": "no", "status": "finalized"},
    }

    def fetch_row(source, source_id):
        probed.append(source_id)
        return venue_rows.get(source_id)  # unknown ids (other modules' rows): not resolved

    settled = settlement_sweep(db, fetch_row=fetch_row, budget=10_000)
    assert settled >= 2  # tolerate other modules' resolvable rows, if any

    assert "test-sweep-pm-1" in probed and "TEST-SWEEP-KX-1" in probed
    assert "test-sweep-pm-2" not in probed  # close in the future: no venue request
    assert "TEST-SWEEP-KX-2" not in probed  # stale-delisted past the recency window

    db.refresh(listed_resolved), db.refresh(delisted_resolved)
    assert listed_resolved.outcome == 1 and listed_resolved.active is False
    assert delisted_resolved.outcome == 0 and delisted_resolved.active is False
    assert listed_resolved in settled_calls  # settle hook got the resolved event
    assert delisted_resolved in settled_calls
    assert still_open not in settled_calls and long_gone not in settled_calls

    # Idempotent: outcomes are recorded, so a re-run never re-settles them.
    probed.clear(), settled_calls.clear()
    settlement_sweep(db, fetch_row=fetch_row, budget=10_000)
    assert "test-sweep-pm-1" not in probed and "TEST-SWEEP-KX-1" not in probed
    assert listed_resolved not in settled_calls and delisted_resolved not in settled_calls


def test_settlement_sweep_requires_trading_module(db, monkeypatch):
    # None in sys.modules makes the import raise even if app.trading exists.
    monkeypatch.setitem(sys.modules, "app.trading", None)
    with pytest.raises(RuntimeError, match="app.trading"):
        settlement_sweep(db, fetch_row=lambda source, source_id: None)
