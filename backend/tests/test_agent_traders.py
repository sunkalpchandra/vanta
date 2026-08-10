"""vanta's autonomous agent-traders: bot creation, strategy firing, idempotency,
standings, and determinism.

Shares the suite SQLite (conftest binds it before app import). All rows are
scoped to source 'test-w7-agents' and categories 'test-w7-*' so other modules'
writes never collide; base rates are pinned by seeding Prediction rows in those
private categories, which makes the deterministic pipeline's forecasts (and thus
each strategy's decision) reproducible. NO network — the pipeline runs with
narratives off, so no LLM call ever fires.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.agent_traders import agent_standings, ensure_agents, run_agents_once
from app.db import Base, SessionLocal, engine  # binding happens in conftest.py
from app.models import AgentTrader, MarketEvent, Position, Prediction, Trade, User
from app.service import learned_base_rate
from app.trading import STARTING_BALANCE

# Pinned base rates via all-YES Predictions in private categories. Unknown
# categories carry the static default 0.42, blended with pseudo_count 20:
#   test-w7-hi : (0.42*20 + 80)/(20+80)   = 0.884
#   test-w7-vhi: (0.42*20 + 120)/(20+120) = 0.9171
CAT_HI, N_HI = "test-w7-hi", 80
CAT_VHI, N_VHI = "test-w7-vhi", 120
CAT_NEUTRAL = "test-w7-neutral"  # unseeded -> base rate stays 0.42

BOT_NAMES = ["vanta-edge", "vanta-confidence", "vanta-contrarian"]


@pytest.fixture(scope="module", autouse=True)
def _seed_base_rates():
    """Seed the pinned-base-rate corpus once for the whole module (idempotent)."""
    # Ensure the schema exists even when this module runs on its own (the full
    # suite gets it from the app lifespan on first TestClient entry).
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for category, n in ((CAT_HI, N_HI), (CAT_VHI, N_VHI)):
            have = db.scalar(select(func.count()).select_from(Prediction).where(Prediction.category == category))
            for i in range(n - (have or 0)):
                db.add(
                    Prediction(
                        question_text=f"w7 {category} {i}",
                        category=category,
                        # Correct-direction probs (outcome=1) so they don't skew
                        # global accuracy/brier; base rate only reads `outcome`.
                        market_probability=0.99,
                        vanta_probability=0.99,
                        outcome=1,
                        # Far in the past so these private rows never surface in
                        # any newest-first track-record view other tests read.
                        resolved_at=datetime(2000, 1, 1, tzinfo=UTC),
                    )
                )
        db.commit()
    yield


def _make_event(category: str, yes_price: float, close_days: int, volume: float = 9_000_000_000.0) -> int:
    """An active, high-volume market that closes `close_days` out. The huge
    volume keeps it at the top of the volume-desc scan so a modest max_markets
    always reaches it, whatever else the suite DB holds."""
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w7-agents",
            source_id=f"w7-{uuid.uuid4().hex}",
            question=f"Will {category} {uuid.uuid4().hex[:6]} resolve YES?",
            category=category,
            active=True,
            yes_price=yes_price,
            outcome=None,
            volume_usd=volume,
            close_time=datetime.now(UTC) + timedelta(days=close_days),
        )
        db.add(event)
        db.commit()
        return event.id


def _bot_user_ids() -> dict[str, int]:
    """user_id of each of MY three strategy bots (the shared DB may also hold a
    foreign AgentTrader created by another module's test — ignore it)."""
    with SessionLocal() as db:
        rows = db.scalars(select(AgentTrader).where(AgentTrader.name.in_(BOT_NAMES))).all()
        return {a.name: a.user_id for a in rows}


def _position(user_id: int, event_id: int) -> Position | None:
    with SessionLocal() as db:
        return db.scalar(
            select(Position).where(Position.user_id == user_id, Position.event_id == event_id)
        )


def _reset_bots() -> None:
    """Wipe MY bots' positions/trades and restore their starting balance —
    reconstructs a clean pre-run state for the determinism check."""
    with SessionLocal() as db:
        uids = [
            a.user_id for a in db.scalars(select(AgentTrader).where(AgentTrader.name.in_(BOT_NAMES))).all()
        ]
        db.query(Trade).filter(Trade.user_id.in_(uids)).delete(synchronize_session=False)
        db.query(Position).filter(Position.user_id.in_(uids)).delete(synchronize_session=False)
        for uid in uids:
            db.get(User, uid).balance = STARTING_BALANCE
        db.commit()


# --- base-rate sanity ---------------------------------------------------------


def test_seeded_base_rates_are_pinned():
    with SessionLocal() as db:
        assert learned_base_rate(db, CAT_HI) == pytest.approx(0.884, abs=1e-4)
        assert learned_base_rate(db, CAT_VHI) == pytest.approx(0.9171, abs=1e-4)
        assert learned_base_rate(db, CAT_NEUTRAL) == pytest.approx(0.42, abs=1e-9)


# --- bot creation -------------------------------------------------------------


def test_ensure_agents_creates_three_bots_idempotently():
    with SessionLocal() as db:
        first = ensure_agents(db)
    assert [a.name for a in first] == BOT_NAMES  # definition order
    assert [a.strategy for a in first] == ["edge", "confidence", "contrarian"]

    with SessionLocal() as db:
        second = ensure_agents(db)
    # Re-running mints nothing new — same rows, same users.
    assert {a.name for a in second} == set(BOT_NAMES)
    assert {a.user_id for a in first} == {a.user_id for a in second}

    with SessionLocal() as db:
        # Scoped to my three strategy bots — the shared DB may also hold a
        # foreign AgentTrader from another module's test.
        mine = db.scalars(select(AgentTrader).where(AgentTrader.name.in_(BOT_NAMES))).all()
        assert len(mine) == 3
        for a in mine:
            user = db.get(User, a.user_id)
            assert user.email == f"{a.name}@bots.vanta"
            assert user.api_key  # a usable trading identity
            assert user.balance == pytest.approx(STARTING_BALANCE)  # untraded yet


# --- strategy firing ----------------------------------------------------------


def test_run_agents_opens_positions_only_where_rules_fire():
    # EDGE: price 0.5, base 0.884, long horizon -> forecast ~0.61, edge ~+0.11.
    edge_id = _make_event(CAT_HI, 0.5, 400)
    # CONF: extreme price 0.05, base 0.917, short horizon -> confidence ~8.2 but
    # edge ~+0.05 (below edge's 0.08 and contrarian's 0.10 gates).
    conf_id = _make_event(CAT_VHI, 0.05, 90)
    # CONTRA: cheap YES at 0.30, base 0.884 -> forecast ~0.44, underpriced ~0.14
    # (fires contrarian, and edge too since |edge| >= 0.08).
    contra_id = _make_event(CAT_HI, 0.30, 400)
    # NEUTRAL: price == base rate (0.42) -> forecast ~0.42, edge ~0 -> nobody.
    neutral_id = _make_event(CAT_NEUTRAL, 0.42, 400)

    with SessionLocal() as db:
        result = run_agents_once(db, max_markets=40)
    assert result["evaluated"] >= 4

    bot = _bot_user_ids()

    # EDGE -> only vanta-edge, buying YES.
    p = _position(bot["vanta-edge"], edge_id)
    assert p is not None and p.side == "yes" and p.shares > 0
    assert _position(bot["vanta-confidence"], edge_id) is None
    assert _position(bot["vanta-contrarian"], edge_id) is None

    # CONF -> only vanta-confidence, buying YES.
    assert _position(bot["vanta-edge"], conf_id) is None
    p = _position(bot["vanta-confidence"], conf_id)
    assert p is not None and p.side == "yes"
    assert _position(bot["vanta-contrarian"], conf_id) is None

    # CONTRA -> vanta-contrarian AND vanta-edge (both buy the cheap YES side).
    assert _position(bot["vanta-contrarian"], contra_id) is not None
    assert _position(bot["vanta-contrarian"], contra_id).side == "yes"
    assert _position(bot["vanta-edge"], contra_id) is not None
    assert _position(bot["vanta-confidence"], contra_id) is None

    # NEUTRAL (forecast ~= price) -> nobody trades.
    for name in BOT_NAMES:
        assert _position(bot[name], neutral_id) is None


# --- idempotency --------------------------------------------------------------


def test_rerun_does_not_double_open():
    event_id = _make_event(CAT_HI, 0.5, 400)  # a fresh edge-firing market
    with SessionLocal() as db:
        run_agents_once(db, max_markets=40)

    edge_uid = _bot_user_ids()["vanta-edge"]
    opened = _position(edge_uid, event_id)
    assert opened is not None
    shares_before = opened.shares

    with SessionLocal() as db:
        second = run_agents_once(db, max_markets=40)
    # No further trade lands on an already-held market.
    assert all(t["event_id"] != event_id for t in second["trades"])
    assert _position(edge_uid, event_id).shares == pytest.approx(shares_before)  # not doubled


# --- standings ----------------------------------------------------------------


def test_agent_standings_returns_the_bots():
    _make_event(CAT_HI, 0.5, 400)
    with SessionLocal() as db:
        run_agents_once(db, max_markets=40)
        standings = agent_standings(db)

    by_name = {s["name"]: s for s in standings}
    # My three strategy bots are all present (a foreign bot may be too).
    assert set(BOT_NAMES) <= by_name.keys()
    assert by_name["vanta-edge"]["strategy"] == "edge"
    assert by_name["vanta-confidence"]["strategy"] == "confidence"
    assert by_name["vanta-contrarian"]["strategy"] == "contrarian"
    for name in BOT_NAMES:
        assert by_name[name].keys() >= {"name", "strategy", "equity", "lifetime_pnl", "n_trades"}
    assert by_name["vanta-edge"]["n_trades"] >= 1  # it has traded by now
    # Ranked best-P&L first among the traded bots.
    traded = [s["lifetime_pnl"] for s in standings if s["n_trades"] > 0]
    assert traded == sorted(traded, reverse=True)


# --- determinism --------------------------------------------------------------


def test_two_runs_on_same_db_yield_identical_trades():
    _make_event(CAT_HI, 0.5, 400)
    _make_event(CAT_VHI, 0.05, 90)

    _reset_bots()
    with SessionLocal() as db:
        first = run_agents_once(db, max_markets=40)["trades"]
    _reset_bots()
    with SessionLocal() as db:
        second = run_agents_once(db, max_markets=40)["trades"]

    assert first == second  # same decisions, sides, and share counts
    assert len(first) >= 2  # at least the edge + confidence markets fired
