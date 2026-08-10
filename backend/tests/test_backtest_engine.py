"""Backtest engine over synthetic MarketEvents.

The events seeded here are INPUTS to the engine (fixtures), not claimed
results — the whole point of the engine is that its outputs are functions of
real ingested data. Sentinel categories ("bt-*") keep the hand-computed
assertions immune to whatever other suite modules write to the shared DB.
"""

import math
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.historian import base_rate_for
from app.agents.orchestrator import run_pipeline
from app.backtest import (
    PSEUDO_COUNT,
    context_for,
    resolved_corpus_timeline,
    run_backtest,
    shrunk_base_rate,
    summarize,
)
from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import BacktestPrediction, MarketEvent, utcnow
from app.quant.scoring import brier_score, directional_accuracy, log_score
from app.routers.backtest import router as backtest_router

SOURCE = "test-bt"
CAT_MAIN = "bt-sports"  # 7-day-horizon corpus
CAT_META = "bt-meta"  # 30-day-horizon hand-computed corpus
CAT_SOLO = "bt-solo"  # single-event category


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # ensures tables exist before direct DB writes
        yield c


def _event(category, outcome, price_7d=None, price_30d=None, volume=50_000.0):
    return MarketEvent(
        source=SOURCE,
        source_id=uuid.uuid4().hex,
        question=f"Will synthetic market {uuid.uuid4().hex[:8]} resolve YES?",
        category=category,
        close_time=utcnow() - timedelta(days=1),
        outcome=outcome,
        volume_usd=volume,
        final_price=None if outcome is None else float(outcome),
        price_7d=price_7d,
        price_30d=price_30d,
        raw={},
    )


@pytest.fixture(scope="module")
def corpus(client):
    """Seed once for the module; every id group is returned for assertions."""
    with SessionLocal() as db:
        main_priced = [
            _event(CAT_MAIN, 1, price_7d=0.75, volume=250_000.0),
            _event(CAT_MAIN, 0, price_7d=0.40, volume=50_000.0),
            _event(CAT_MAIN, 1, price_7d=0.55, volume=1_500_000.0),
            _event(CAT_MAIN, 0, price_7d=0.20, volume=10_000.0),
        ]
        main_unpriced = _event(CAT_MAIN, 1)  # resolved, no pre-close price
        main_unresolved = _event(CAT_MAIN, None, price_7d=0.60)
        meta_priced = [
            _event(CAT_META, 1, price_30d=0.80, volume=10_000.0),
            _event(CAT_META, 0, price_30d=0.30, volume=20_000.0),
            _event(CAT_META, 1, price_30d=0.60, volume=30_000.0),
            _event(CAT_META, 0, price_30d=0.70, volume=40_000.0),
        ]
        meta_unpriced = _event(CAT_META, 1)  # counted in the corpus, never scored
        solo = _event(CAT_SOLO, 1)
        rows = [*main_priced, main_unpriced, main_unresolved, *meta_priced, meta_unpriced, solo]
        db.add_all(rows)
        db.commit()
        ids = {
            "main_priced": [e.id for e in main_priced],
            "main_unpriced": main_unpriced.id,
            "main_unresolved": main_unresolved.id,
            "meta_priced": [e.id for e in meta_priced],
            "meta_unpriced": meta_unpriced.id,
        }
    return ids


def _scored_ids(db, horizon_days):
    return set(
        db.scalars(
            select(BacktestPrediction.event_id).where(BacktestPrediction.horizon_days == horizon_days)
        ).all()
    )


def test_scores_only_resolved_events_with_preclose_price(corpus):
    with SessionLocal() as db:
        run_backtest(db, horizon_days=7)
        scored = _scored_ids(db, 7)
        assert set(corpus["main_priced"]) <= scored
        assert corpus["main_unpriced"] not in scored  # resolved but no T-7 price
        assert corpus["main_unresolved"] not in scored  # priced but unresolved
        assert set(corpus["meta_priced"]).isdisjoint(scored)  # 30d prices only


def test_base_rate_is_strictly_temporal(corpus):
    """An event's prior may only learn from events that closed BEFORE it —
    never later resolutions, never itself. (The first version used corpus-wide
    leave-one-out, which let the future leak into every prior.)"""
    with SessionLocal() as db:
        timeline = resolved_corpus_timeline(db)
    # Timeline is close-time ascending and excludes unresolved rows.
    times = [t for t, _, _ in timeline]
    assert times == sorted(times)
    assert all(outcome in (0, 1) for _, _, outcome in timeline)
    # Cumulative prefix semantics: the prior for a hypothetical event closing
    # at timeline[k]'s close counts exactly the k earlier events.
    static = base_rate_for(CAT_MAIN)
    main_rows = [(t, o) for t, c, o in timeline if c == CAT_MAIN]
    cutoff = main_rows[-1][0]  # the last main-category close
    prior_rows = [o for t, o in main_rows if t < cutoff]
    expected = (static * PSEUDO_COUNT + sum(prior_rows)) / (PSEUDO_COUNT + len(prior_rows))
    assert shrunk_base_rate(CAT_MAIN, len(prior_rows), sum(prior_rows)) == pytest.approx(expected)
    # Nothing settled yet -> the static prior stands.
    assert shrunk_base_rate(CAT_SOLO, 0, 0) == base_rate_for(CAT_SOLO)
    assert shrunk_base_rate("bt-nonexistent", 0, 0) == base_rate_for("bt-nonexistent")


def test_rerun_is_idempotent(corpus):
    with SessionLocal() as db:
        run_backtest(db, horizon_days=7)
        before = _scored_ids(db, 7)
        result = run_backtest(db, horizon_days=7)
        assert result["n_scored"] == 0
        assert result["n_total"] == len(before)
        assert _scored_ids(db, 7) == before
        # The unique index is the backstop against concurrent runs.
        db.add(
            BacktestPrediction(
                event_id=corpus["main_priced"][0],
                horizon_days=7,
                market_probability=0.5,
                vanta_probability=0.5,
                outcome=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_market_and_vanta_scored_on_identical_inputs(corpus):
    event_id = corpus["main_priced"][0]
    with SessionLocal() as db:
        run_backtest(db, horizon_days=7)
        event = db.get(MarketEvent, event_id)
        stored = db.scalar(
            select(BacktestPrediction).where(
                BacktestPrediction.event_id == event_id, BacktestPrediction.horizon_days == 7
            )
        )
        # The market side is exactly the T-7 price the pipeline was given.
        assert stored.market_probability == event.price_7d
        # Rebuilding the same context reproduces vanta's number exactly:
        # deterministic pipeline, identical information for both sides. The
        # prior counts only events that closed before this one.
        close = event.close_time
        prior = [
            outcome
            for t, cat, outcome in resolved_corpus_timeline(db)
            if cat == event.category and t < close
        ]
        base_rate = shrunk_base_rate(event.category, len(prior), sum(prior))
        ctx = context_for(event, 7, base_rate)
        assert ctx.evidence == [] and ctx.narratives is False
        assert ctx.analog_corpus == []  # hindsight fixture disabled in backtests
        assert run_pipeline(ctx).probability == stored.vanta_probability
        assert stored.outcome == event.outcome


def test_summarize_matches_hand_computed_example(corpus):
    with SessionLocal() as db:
        run_backtest(db, horizon_days=30)
        s = summarize(db, 30, category=CAT_META)
        stored = db.scalars(
            select(BacktestPrediction)
            .join(MarketEvent, BacktestPrediction.event_id == MarketEvent.id)
            .where(BacktestPrediction.horizon_days == 30, MarketEvent.category == CAT_META)
        ).all()
        vanta_pairs = [(p.vanta_probability, p.outcome) for p in stored]

    # 4 scored of 5 resolved in the category (one lacks a pre-close price).
    assert s["n"] == 4
    assert s["n_resolved_corpus"] == 5
    assert s["coverage"] == pytest.approx(0.8)
    # Market side, by hand: prices .8/.3/.6/.7 against outcomes 1/0/1/0.
    assert s["market_brier"] == pytest.approx((0.04 + 0.09 + 0.16 + 0.49) / 4)
    assert s["market_accuracy"] == pytest.approx(3 / 4)  # the 0.7-on-NO misses
    expected_log = -(math.log(0.8) + math.log(1 - 0.3) + math.log(0.6) + math.log(1 - 0.7)) / 4
    assert s["market_log"] == pytest.approx(expected_log, abs=1e-4)
    # No-skill benchmark: always predict the 50% corpus rate -> Brier 0.25.
    assert s["outcome_base_rate"] == pytest.approx(0.5)
    assert s["base_rate_brier"] == pytest.approx(0.25)
    # vanta side agrees with the scoring helpers over the stored pairs.
    assert s["vanta_brier"] == round(brier_score(vanta_pairs), 4)
    assert s["vanta_log"] == round(log_score(vanta_pairs), 4)
    assert s["vanta_accuracy"] == round(directional_accuracy(vanta_pairs), 4)
    # Honest framing fields.
    assert s["sources"] == {SOURCE: 4}
    assert s["median_volume_usd"] == pytest.approx(25_000.0)
    # Calibration: each market price lands in its own bin with its outcome.
    bins = {round(b["mid"], 2): b for b in s["calibration"]}
    assert sum(b["vanta_count"] for b in s["calibration"]) == 4
    for mid, price, outcome in [(0.85, 0.80, 1.0), (0.35, 0.30, 0.0), (0.65, 0.60, 1.0), (0.75, 0.70, 0.0)]:
        assert bins[mid]["market_count"] == 1
        assert bins[mid]["market_mean_predicted"] == pytest.approx(price)
        assert bins[mid]["market_observed_rate"] == pytest.approx(outcome)


def test_router_endpoints(corpus):
    with SessionLocal() as db:
        run_backtest(db, horizon_days=30)
    local = FastAPI()
    local.include_router(backtest_router)
    with TestClient(local) as c:
        ok = c.get("/api/backtest/real", params={"horizon": 30, "category": CAT_META})
        assert ok.status_code == 200
        assert ok.json()["n"] == 4
        bins = c.get("/api/backtest/real/calibration", params={"horizon": 30, "category": CAT_META})
        assert bins.status_code == 200
        assert len(bins.json()) == 10
        empty = c.get("/api/backtest/real", params={"horizon": 7, "category": "bt-nonexistent"})
        assert empty.status_code == 404
        assert "run" in empty.json()["detail"]
        assert c.get("/api/backtest/real", params={"horizon": 12}).status_code == 422
        ran = c.post("/api/backtest/run", params={"horizon": 7, "limit": 5})
        assert ran.status_code == 200
        assert ran.json()["n_scored"] == 0  # everything eligible is already scored
        assert c.post("/api/backtest/run", params={"horizon": 7, "limit": 9999}).status_code == 422


def test_frozen_scorecard_artifact_is_valid():
    """The committed frozen scorecard must stay loadable and honest: real n,
    both forecasters scored, and a computed_at stamp."""
    from app.routers.backtest import FROZEN_PATH, load_frozen

    assert FROZEN_PATH.exists()
    frozen = load_frozen(7, None)
    assert frozen is not None and frozen["frozen"] is True
    assert frozen["n"] > 0 and frozen["computed_at"]
    assert frozen["vanta_brier"] is not None and frozen["market_brier"] is not None
    assert load_frozen(7, "technology") is None  # no per-category slices stored
