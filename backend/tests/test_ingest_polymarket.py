"""Polymarket ingest: normalizer, price_at leakage guard, upsert idempotence.

The fixture dicts are real gamma-api markets (sampled live 2026-08-10),
trimmed to the fields the normalizer reads. No test touches the network.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.ingest.polymarket import normalize, normalize_category, price_at, upsert_events
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent

# AMM-era YES resolution: prices settle a hair off 1/0, category field set.
MARKET_YES = {
    "id": "104348",
    "question": "Will inflation be 0.5% or more from February to March?",
    "category": "US-current-affairs",
    "endDate": "2021-04-13T00:00:00Z",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.999999853825246736755669589996929", "0.000000146174753263244330410003071001257"]',
    "volume": "44354.363851",
    "volumeNum": 44354.36,
    "clobTokenIds": (
        '["57395419369815508619741213499898084963041685385575858601378574306859428141129",'
        ' "73225148250615903566085382792791554761249101706979619151295754602169322343226"]'
    ),
    "closed": True,
    "closedTime": "2021-04-14 20:43:26+00",
}

# AMM-era NO resolution.
MARKET_NO = {
    "id": "104027",
    "question": "Will the US have fewer than 35,000 new COVID-19 cases on any day before April 7, 2021?",
    "category": "Coronavirus",
    "endDate": "2021-04-07T00:00:00Z",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.00000008122937106443880973670710621756454", "0.9999999187706289355611902632928938"]',
    "volume": "169609.598266",
    "volumeNum": 169609.6,
    "clobTokenIds": (
        '["47462789971153179633659857068275327496255596665674637985237415148881664288309",'
        ' "73510098371845198558637374430298045639049580304887607315548837638484201838245"]'
    ),
    "closed": True,
    "closedTime": "2021-04-08 20:20:16+00",
}

# '["0", "0"]' — closed, but the resolution never reached the API.
MARKET_AMBIGUOUS = {
    "id": "12",
    "question": "Will Joe Biden get Coronavirus before the election?",
    "category": "US-current-affairs",
    "endDate": "2020-11-04T00:00:00Z",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0", "0"]',
    "volume": "32257.445115",
    "volumeNum": 32257.45,
    "clobTokenIds": (
        '["53135072462907880191400140706440867753044989936304433583131786753949599718775",'
        ' "60869871469376321574904667328762911501870754872924453995477779862968218702336"]'
    ),
    "closed": True,
    "closedTime": "2020-11-02 16:31:01+00",
}

# CLOB-era: exact "1"/"0" prices, no category field — tags carry the signal.
MARKET_CLOB_YES = {
    "id": "3477970",
    "question": "Ethereum above 1,850 on August 10, 4AM ET?",
    "endDate": "2026-08-10T08:00:00Z",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["1", "0"]',
    "volume": "115",
    "volumeNum": 115,
    "clobTokenIds": (
        '["49559364172232833322038217217604980711839571080776308943852375407811619179038",'
        ' "80838559041185190214269977522023163599534298237782668184345141948663549764029"]'
    ),
    "tags": [{"label": "Ethereum"}, {"label": "Crypto"}, {"label": "Crypto Prices"}, {"label": "Recurring"}],
    "closed": True,
    "closedTime": "2026-08-10 08:11:33+00",
}

# Six scalar buckets — not a binary market.
MARKET_MULTI = {
    "id": "103999",
    "question": "How many more tweets will be on the @mtgreenee account on March 22, 2021?",
    "category": "US-current-affairs",
    "endDate": "2021-03-22T00:00:00Z",
    "outcomes": '["Less than 80", "80-95", "96-110", "111-125", "126-140", "More than 140"]',
    "outcomePrices": (
        '["0.0000003217877262999883952109747405051791", "0.9999983818228862567963016807360445",'
        ' "0.0000003355293792539112221415635405899405", "0.000000325726831459699116531793339046128",'
        ' "0.0000003162824510381640699838699898722317", "0.0000003188507256914408944510623450210309"]'
    ),
    "volume": "59494.679271",
    "volumeNum": 59494.68,
    "closed": True,
    "closedTime": "2021-03-23 19:14:57+00",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # ensures tables exist before direct DB writes
        yield c


def test_normalize_yes_winner():
    row = normalize(MARKET_YES)
    assert row is not None
    assert row["source"] == "polymarket"
    assert row["source_id"] == "104348"
    assert row["outcome"] == 1
    assert row["category"] == "politics"
    assert row["close_time"] == datetime(2021, 4, 13, tzinfo=UTC)
    assert row["volume_usd"] == 44354.36
    assert row["final_price"] == pytest.approx(1.0, abs=1e-6)  # YES side
    assert len(row["raw"]["clobTokenIds"]) == 2  # kept for the price pass
    assert row["raw"]["clobTokenIds"][0].startswith("57395419")


def test_normalize_no_winner():
    row = normalize(MARKET_NO)
    assert row is not None
    assert row["outcome"] == 0
    assert row["category"] == "science"  # Coronavirus
    assert row["final_price"] == pytest.approx(0.0, abs=1e-6)


def test_normalize_ambiguous_prices_leave_outcome_unknown():
    row = normalize(MARKET_AMBIGUOUS)
    assert row is not None
    assert row["outcome"] is None
    assert row["final_price"] == 0.0


def test_normalize_clob_era_exact_prices_and_tag_category():
    row = normalize(MARKET_CLOB_YES)
    assert row is not None
    assert row["outcome"] == 1
    assert row["category"] == "crypto"  # no category field; "Crypto" tag wins
    assert row["final_price"] == 1.0
    assert row["volume_usd"] == 115.0


def test_normalize_rejects_junk():
    assert normalize(MARKET_MULTI) is None  # six buckets, not binary
    assert normalize({**MARKET_YES, "question": "  "}) is None
    assert normalize({**MARKET_YES, "endDate": "soon"}) is None
    assert normalize({**MARKET_YES, "endDate": None}) is None
    assert normalize({**MARKET_YES, "outcomes": '["Long", "Short"]'}) is None
    assert normalize({**MARKET_YES, "id": ""}) is None


def test_normalize_split_final_prices_mean_no_outcome():
    row = normalize({**MARKET_YES, "outcomePrices": '["0.62", "0.38"]'})
    assert row is not None
    assert row["outcome"] is None  # nobody settled at ~1
    assert row["final_price"] == 0.62


@pytest.mark.parametrize(
    ("category", "tags", "expected"),
    [
        ("US-current-affairs", [], "politics"),
        ("Coronavirus", [], "science"),
        ("Crypto", [], "crypto"),
        ("NFTs", [], "crypto"),
        ("Business", [], "finance"),
        ("Sports", [], "sports"),
        ("Space", [], "science"),
        ("Tech", [], "technology"),
        ("Pop-Culture ", [], "other"),
        (None, ["Ethereum", "Crypto"], "crypto"),
        (None, ["Recurring", "U.S. Politics"], "politics"),
        (None, [], "other"),
    ],
)
def test_normalize_category(category, tags, expected):
    assert normalize_category(category, tags) == expected


def _ts(*args) -> int:
    return int(datetime(*args, tzinfo=UTC).timestamp())


def test_price_at_never_reads_after_the_cutoff():
    """The leakage guard: a point after T-h must be ignored even when it is
    far closer to the cutoff than any point before it."""
    close = datetime(2021, 4, 7, tzinfo=UTC)  # 7d cutoff = 2021-03-31 00:00
    history = [
        {"t": _ts(2021, 3, 24), "p": 0.30},
        {"t": _ts(2021, 3, 30, 12), "p": 0.40},
        {"t": _ts(2021, 3, 31, 0, 0, 1), "p": 0.95},  # 1s late: leakage
    ]
    assert price_at(history, close, 7) == 0.40
    assert price_at(list(reversed(history)), close, 7) == 0.40  # order-proof


def test_price_at_exact_cutoff_point_counts():
    close = datetime(2021, 4, 7, tzinfo=UTC)
    history = [{"t": _ts(2021, 3, 31), "p": 0.55}]
    assert price_at(history, close, 7) == 0.55


def test_price_at_without_early_history_returns_none():
    close = datetime(2021, 4, 7, tzinfo=UTC)
    assert price_at([], close, 7) is None
    assert price_at([{"t": _ts(2021, 4, 6), "p": 0.9}], close, 30) is None


def test_price_at_treats_naive_close_time_as_utc():
    """SQLite hands back naive datetimes; they must mean UTC, not local."""
    history = [{"t": _ts(2021, 3, 30), "p": 0.4}, {"t": _ts(2021, 3, 31, 1), "p": 0.9}]
    aware = price_at(history, datetime(2021, 4, 7, tzinfo=UTC), 7)
    naive = price_at(history, datetime(2021, 4, 7), 7)
    assert naive == aware == 0.4


def test_upsert_skips_existing_rows(client):
    row = normalize(MARKET_YES)
    with SessionLocal() as db:
        kept, skipped = upsert_events(db, [row])
        db.commit()
        assert (kept, skipped) == (1, 0)
        kept, skipped = upsert_events(db, [row])
        db.commit()
        assert (kept, skipped) == (0, 1)
        stored = db.scalars(
            select(MarketEvent).where(MarketEvent.source == "polymarket", MarketEvent.source_id == "104348")
        ).all()
    assert len(stored) == 1
    assert stored[0].outcome == 1
    assert stored[0].raw["clobTokenIds"][0].startswith("57395419")


def test_upsert_dedupes_within_one_batch(client):
    row = normalize(MARKET_NO)
    with SessionLocal() as db:
        kept, skipped = upsert_events(db, [row, dict(row)])
        db.commit()
        assert (kept, skipped) == (1, 1)
        count = len(
            db.scalars(
                select(MarketEvent).where(MarketEvent.source == "polymarket", MarketEvent.source_id == "104027")
            ).all()
        )
    assert count == 1
