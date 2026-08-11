"""Agent-trader performance dashboard endpoint (/api/agent-traders).

Shares the suite SQLite (conftest binds it before app import). The three real
bots are GLOBAL (keyed by name via ensure_agents) and other modules assert they
stay untraded, so this module NEVER trades with them — the trade-reflection test
uses a dedicated module-local bot ('test-w10-tradebot') on its own market events
(source 'test-w10-agent-dashboard'), leaving the shared bots' balances pristine.
No network: the local bot registers a usable trading identity (api_key) and
trades through the real engine via that key.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent_traders import ensure_agents
from app.db import Base, SessionLocal, engine
from app.main import app  # DB binding happens in conftest.py
from app.models import AgentTrader, MarketEvent, User
from app.routers import agent_dashboard
from app.trading import STARTING_BALANCE

# The router isn't wired into app.main yet — that's an integration step. Mount it
# here so this suite can exercise the endpoint, guarded so it stays a no-op once
# main.py registers it for real (otherwise a duplicate route would pile up).
if not any(getattr(r, "path", None) == "/api/agent-traders" for r in app.routes):
    app.include_router(agent_dashboard.router)

BOT_NAMES = {"vanta-edge", "vanta-confidence", "vanta-contrarian"}
STRATEGY_BY_NAME = {
    "vanta-edge": "edge",
    "vanta-confidence": "confidence",
    "vanta-contrarian": "contrarian",
}
ROW_KEYS = {"name", "strategy", "equity", "lifetime_pnl", "n_trades", "n_positions", "balance"}

# A dedicated bot only this module trades with, so the three shared bots stay
# untraded for other modules that assert exactly that.
LOCAL_BOT = "test-w10-tradebot"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def _bots():
    """Create the three bots once (idempotent). The endpoint itself never seeds
    them — this fixture stands in for the background runner that would."""
    # Ensure the schema exists even when this module runs on its own (the full
    # suite gets it from the app lifespan on first TestClient entry).
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_agents(db)
    yield


def _make_event(yes_price: float = 0.4) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w10-agent-dashboard",
            source_id=f"w10ad-{uuid.uuid4().hex}",
            question=f"Will w10 dash probe {uuid.uuid4().hex[:8]} resolve YES?",
            category="technology",
            active=True,
            yes_price=yes_price,
            outcome=None,
        )
        db.add(event)
        db.commit()
        return event.id


def _make_local_bot() -> str:
    """Create this module's private agent-trader (an AgentTrader backed by its
    own bot User) and return its api_key. Idempotent on the reserved name.
    run_agents_once only ever drives the three ensure_agents bots, so this one
    stays inert except for the explicit trade below."""
    with SessionLocal() as db:
        bot = db.scalar(select(AgentTrader).where(AgentTrader.name == LOCAL_BOT))
        if bot is not None:
            return db.get(User, bot.user_id).api_key
        user = User(email=f"{LOCAL_BOT}@bots.vanta", api_key=f"vk_bot_{uuid.uuid4().hex}")
        db.add(user)
        db.flush()  # assign user.id before the AgentTrader references it
        db.add(AgentTrader(name=LOCAL_BOT, strategy="edge", user_id=user.id))
        db.commit()
        return user.api_key


def _by_name(client) -> dict:
    resp = client.get("/api/agent-traders")
    assert resp.status_code == 200
    return {r["name"]: r for r in resp.json()}


# --- shape --------------------------------------------------------------------


def test_lists_the_three_bots_with_strategies(client):
    by_name = _by_name(client)
    assert set(by_name) >= BOT_NAMES  # a foreign bot, if any, is tolerated
    for name in BOT_NAMES:
        row = by_name[name]
        assert set(row) == ROW_KEYS
        assert row["strategy"] == STRATEGY_BY_NAME[name]
        assert isinstance(row["n_trades"], int)
        assert isinstance(row["n_positions"], int)
        # lifetime P&L is always equity above the ⓥ10,000 starting bankroll.
        assert row["lifetime_pnl"] == pytest.approx(round(row["equity"] - STARTING_BALANCE, 2))


def test_returns_exactly_the_agent_trader_rows(client):
    """Purely reflective — one row per AgentTrader, nothing seeded on read."""
    rows = client.get("/api/agent-traders").json()
    with SessionLocal() as db:
        n_bots = db.scalar(select(func.count(AgentTrader.id)))
    assert len(rows) == n_bots


def test_endpoint_is_deterministic(client):
    first = client.get("/api/agent-traders").json()
    second = client.get("/api/agent-traders").json()
    assert first == second


# --- a trade shows up in the standing -----------------------------------------


def test_trade_reflects_in_standing(client):
    api_key = _make_local_bot()

    # Fresh bot: it shows up flat before it trades.
    before = _by_name(client)[LOCAL_BOT]
    assert before["strategy"] == "edge"
    assert before["n_trades"] == 0
    assert before["n_positions"] == 0
    assert before["balance"] == pytest.approx(STARTING_BALANCE)
    assert before["equity"] == pytest.approx(STARTING_BALANCE)
    assert before["lifetime_pnl"] == pytest.approx(0.0)

    event_id = _make_event(yes_price=0.4)
    resp = client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": "yes", "action": "buy", "shares": 100},  # cost ⓥ40
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200

    after = _by_name(client)[LOCAL_BOT]
    assert after["n_trades"] == 1
    assert after["n_positions"] == 1
    assert after["balance"] == pytest.approx(9960.0)  # 10000 - 100 × ⓥ0.40
    # The lot is marked at the same venue price it filled at, so equity is
    # unchanged and lifetime P&L stays ~0 (equity above the starting bankroll).
    assert after["equity"] == pytest.approx(10_000.0)
    assert after["lifetime_pnl"] == pytest.approx(0.0)
