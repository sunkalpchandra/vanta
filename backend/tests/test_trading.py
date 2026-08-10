"""Play-money trading lifecycle: register → buy → average up → sell → settle.

Shares the suite SQLite (conftest binds it before app import); every test
creates its own users and synthetic MarketEvents (source 'test-trade'), so
other modules' writes never matter here.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent, User
from app.trading import settle_event

# Until main.py wires the router (shared file — integration step), mount it
# here. The guard makes this a no-op once main.py includes it.

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _auth(user: dict) -> dict:
    return {"X-API-Key": user["api_key"]}


def _make_event(yes_price=0.4, active=True, outcome=None, question=None, **kwargs) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-trade",
            source_id=f"tt-{uuid.uuid4().hex}",
            question=question or f"Will synthetic market {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=active,
            yes_price=yes_price,
            outcome=outcome,
            **kwargs,
        )
        db.add(event)
        db.commit()
        return event.id


def _set_price(event_id: int, yes_price: float) -> None:
    with SessionLocal() as db:
        db.get(MarketEvent, event_id).yes_price = yes_price
        db.commit()


def _db_balance(user_id: int) -> float:
    with SessionLocal() as db:
        return db.get(User, user_id).balance


def _trade(client, user, event_id, side, action, shares):
    return client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers=_auth(user),
    )


# --- identity -----------------------------------------------------------------


def test_trade_without_key_is_401(client):
    event_id = _make_event()
    body = {"side": "yes", "action": "buy", "shares": 10}
    assert client.post(f"/api/markets/{event_id}/trade", json=body).status_code == 401
    resp = client.post(f"/api/markets/{event_id}/trade", json=body, headers={"X-API-Key": "vk_bogus"})
    assert resp.status_code == 401


# --- buys ---------------------------------------------------------------------


def test_buy_yes_moves_balance_and_opens_position(client):
    user = _register(client, "buyer")
    event_id = _make_event(yes_price=0.4)
    resp = _trade(client, user, event_id, "yes", "buy", 100)
    assert resp.status_code == 200
    body = resp.json()
    assert body["trade"]["price"] == pytest.approx(0.4)
    assert body["trade"]["cost"] == pytest.approx(-40.0)  # signed delta: spent
    assert body["balance"] == pytest.approx(9960.0)
    assert body["position"]["shares"] == pytest.approx(100)
    assert body["position"]["avg_price"] == pytest.approx(0.4)
    assert body["note"] == "play money · paper trading · real market prices"
    assert _db_balance(user["id"]) == pytest.approx(9960.0)


def test_second_buy_weights_average_and_partial_sell_realizes_pnl(client):
    user = _register(client, "averager")
    event_id = _make_event(yes_price=0.4)
    _trade(client, user, event_id, "yes", "buy", 100)  # cost 40
    _set_price(event_id, 0.5)
    body = _trade(client, user, event_id, "yes", "buy", 100).json()  # cost 50
    assert body["balance"] == pytest.approx(9910.0)
    assert body["position"]["shares"] == pytest.approx(200)
    assert body["position"]["avg_price"] == pytest.approx(0.45)

    _set_price(event_id, 0.6)
    body = _trade(client, user, event_id, "yes", "sell", 50).json()
    assert body["trade"]["cost"] == pytest.approx(30.0)  # proceeds credited
    assert body["balance"] == pytest.approx(9940.0)
    assert body["position"]["shares"] == pytest.approx(150)
    assert body["position"]["avg_price"] == pytest.approx(0.45)  # basis unchanged by sells
    assert body["position"]["realized_pnl"] == pytest.approx(7.5)  # 50 * (0.6 - 0.45)

    # detail endpoint shows my position with a key, hides it without
    detail = client.get(f"/api/markets/{event_id}", headers=_auth(user)).json()
    assert [p["shares"] for p in detail["my_positions"]] == [pytest.approx(150)]
    assert client.get(f"/api/markets/{event_id}").json()["my_positions"] == []


def test_no_side_prices_at_complement(client):
    user = _register(client, "contrarian")
    event_id = _make_event(yes_price=0.4)  # NO trades at 0.6
    body = _trade(client, user, event_id, "no", "buy", 10).json()
    assert body["trade"]["price"] == pytest.approx(0.6)
    assert body["balance"] == pytest.approx(9994.0)

    _set_price(event_id, 0.3)  # NO now worth 0.7
    body = _trade(client, user, event_id, "no", "sell", 10).json()
    assert body["trade"]["cost"] == pytest.approx(7.0)
    assert body["balance"] == pytest.approx(10001.0)
    assert body["position"]["shares"] == pytest.approx(0.0)  # row survives as history
    assert body["position"]["realized_pnl"] == pytest.approx(1.0)  # 10 * (0.7 - 0.6)


# --- rejections ---------------------------------------------------------------


def test_insufficient_balance_is_409(client):
    user = _register(client, "broke")
    event_id = _make_event(yes_price=0.4)
    resp = _trade(client, user, event_id, "yes", "buy", 50_000)  # cost 20k > 10k
    assert resp.status_code == 409
    assert "insufficient balance" in resp.json()["detail"]
    assert _db_balance(user["id"]) == pytest.approx(10_000.0)  # untouched


def test_untradeable_events_are_409(client):
    user = _register(client, "blocked")
    for event_id in (
        _make_event(active=False),  # inactive
        _make_event(active=True, outcome=1),  # resolved
        _make_event(yes_price=None),  # never synced
        _make_event(yes_price=1.0),  # not strictly inside (0, 1)
    ):
        assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 409


def test_sell_capped_at_held_and_empty_sell_rejected(client):
    user = _register(client, "capper")
    event_id = _make_event(yes_price=0.4)
    _trade(client, user, event_id, "yes", "buy", 100)
    body = _trade(client, user, event_id, "yes", "sell", 500).json()
    assert body["trade"]["shares"] == pytest.approx(100)  # capped at held
    assert body["position"]["shares"] == pytest.approx(0.0)
    assert body["balance"] == pytest.approx(10_000.0)  # round trip at one price
    assert _trade(client, user, event_id, "yes", "sell", 1).status_code == 409


# --- settlement ---------------------------------------------------------------


def test_settlement_pays_winners_exactly_and_is_idempotent(client):
    winner = _register(client, "winner")
    loser = _register(client, "loser")
    event_id = _make_event(yes_price=0.4)
    _trade(client, winner, event_id, "yes", "buy", 100)  # cost 40 -> 9960
    _trade(client, loser, event_id, "no", "buy", 100)  # cost 60 -> 9940

    with SessionLocal() as db:
        event = db.get(MarketEvent, event_id)
        event.outcome = 1
        event.active = False
        db.commit()
        assert settle_event(db, event) == 2
    assert _db_balance(winner["id"]) == pytest.approx(10_060.0)  # +100 payout
    assert _db_balance(loser["id"]) == pytest.approx(9940.0)  # side lost: no credit

    with SessionLocal() as db:  # idempotent: nothing left, balances stay put
        assert settle_event(db, db.get(MarketEvent, event_id)) == 0
    assert _db_balance(winner["id"]) == pytest.approx(10_060.0)
    assert _db_balance(loser["id"]) == pytest.approx(9940.0)

    pf = client.get("/api/markets/portfolio/me", headers=_auth(winner)).json()
    assert pf["realized_pnl_total"] == pytest.approx(60.0)  # 100 * (1 - 0.4)
    assert all(p["settled"] for p in pf["positions"])
    assert pf["equity"] == pytest.approx(10_060.0)  # settled positions carry no mark


# --- portfolio ----------------------------------------------------------------


def test_portfolio_equity_hand_computed(client):
    user = _register(client, "folio")
    event_id = _make_event(yes_price=0.4)
    _trade(client, user, event_id, "yes", "buy", 50)  # cost 20 -> 9980
    _trade(client, user, event_id, "no", "buy", 20)  # cost 12 -> 9968
    _set_price(event_id, 0.5)

    assert client.get("/api/markets/portfolio/me").status_code == 401
    pf = client.get("/api/markets/portfolio/me", headers=_auth(user)).json()
    assert pf["balance"] == pytest.approx(9968.0)
    by_side = {p["side"]: p for p in pf["positions"]}
    assert by_side["yes"]["unrealized_pnl"] == pytest.approx(5.0)  # 50 * (0.5 - 0.4)
    assert by_side["no"]["unrealized_pnl"] == pytest.approx(-2.0)  # 20 * (0.5 - 0.6)
    assert by_side["no"]["current_price"] == pytest.approx(0.5)
    # equity marks to market: 9968 + 50*0.5 + 20*0.5
    assert pf["equity"] == pytest.approx(10_003.0)
    assert pf["realized_pnl_total"] == pytest.approx(0.0)


# --- leaderboard --------------------------------------------------------------


def test_leaderboard_ranks_by_lifetime_pnl_and_skips_non_traders(client):
    alpha = _register(client, "alpha")
    beta = _register(client, "idle")  # registers but never trades
    gamma = _register(client, "gamma")
    event_id = _make_event(yes_price=0.5)
    _trade(client, alpha, event_id, "yes", "buy", 100)  # 9950 + 100 shares
    _trade(client, gamma, event_id, "yes", "buy", 10)  # 9995 + 10 shares
    _set_price(event_id, 0.8)

    rows = client.get("/api/markets/traders?limit=100").json()["traders"]
    ids = [r["user_id"] for r in rows]
    assert beta["id"] not in ids  # zero trades -> excluded
    mine = {r["user_id"]: r for r in rows}
    assert mine[alpha["id"]]["lifetime_pnl"] == pytest.approx(30.0)  # 9950 + 80 - 10000
    assert mine[gamma["id"]]["lifetime_pnl"] == pytest.approx(3.0)  # 9995 + 8 - 10000
    assert ids.index(alpha["id"]) < ids.index(gamma["id"])
    assert "@" not in mine[alpha["id"]]["name"]  # emails never leak


# --- listing ------------------------------------------------------------------


def test_market_list_filters_and_paginates(client):
    token = f"zx{uuid.uuid4().hex[:10]}"
    active_id = _make_event(yes_price=0.35, question=f"Will {token} ship this quarter?")
    settled_id = _make_event(yes_price=None, active=False, outcome=0, question=f"Did {token} ship last quarter?")

    active = client.get(f"/api/markets?status=active&q={token}").json()
    assert active["total"] == 1
    assert [i["id"] for i in active["items"]] == [active_id]
    assert active["items"][0]["yes_price"] == pytest.approx(0.35)

    settled = client.get(f"/api/markets?status=settled&q={token}").json()
    assert settled["total"] == 1
    assert [i["id"] for i in settled["items"]] == [settled_id]
    assert settled["items"][0]["outcome"] == 0

    assert client.get(f"/api/markets?q={token}&limit=101").status_code == 422
    assert client.get(f"/api/markets?q={token}&status=paused").status_code == 422
    page = client.get(f"/api/markets?q={token}&limit=1&offset=1").json()
    assert page["total"] == 1 and page["items"] == []  # past the end, count intact
    assert client.get("/api/markets?sort=close_time").status_code == 200


def _make_active_event(db, price=0.4, source_id="dust-1"):
    from app.models import MarketEvent

    ev = MarketEvent(
        source="test-trade", source_id=source_id, question="Dust pump probe?",
        category="other", active=True, yes_price=price, outcome=None,
    )
    db.add(ev)
    db.commit()
    return ev


def test_dust_sells_cannot_mint_credits(client):
    """The round-6 money pump: buy a lot, then liquidate in sub-cent slices —
    balance must never exceed the fair single-sell value."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Position, User
    from app.trading import execute_trade

    reg = client.post("/api/users", json={"email": "dust-pumper@example.com"})
    key = reg.json()["api_key"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.api_key == key))
        ev = _make_active_event(db, price=0.4, source_id="dust-sell")
        start = user.balance
        execute_trade(db, user, ev, "yes", "buy", 100)  # fair buy: ⓥ40
        # Try to skim: 0.013-share slices each worth ⓥ0.0052.
        for _ in range(200):
            try:
                execute_trade(db, user, ev, "yes", "sell", 0.013)
            except Exception:
                break
        # Liquidate whatever remains as a full exit.
        pos = db.scalar(select(Position).where(Position.user_id == user.id, Position.event_id == ev.id))
        if pos and pos.shares > 0:
            execute_trade(db, user, ev, "yes", "sell", pos.shares)
        db.refresh(user)
        # A fair round trip at an unchanged price can only lose to rounding.
        assert user.balance <= start + 1e-9


def test_dust_buys_cannot_mint_credits(client):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User
    from app.trading import TradeError, execute_trade

    reg = client.post("/api/users", json={"email": "dust-buyer@example.com"})
    key = reg.json()["api_key"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.api_key == key))
        ev = _make_active_event(db, price=0.01, source_id="dust-buy")
        # Sub-cent-notional buys are rejected outright now.
        with pytest.raises(TradeError):
            execute_trade(db, user, ev, "yes", "buy", 0.5)  # notional ⓥ0.005


def test_trading_halts_past_close(client):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import MarketEvent, User
    from app.trading import TradeError, execute_trade

    reg = client.post("/api/users", json={"email": "late-trader@example.com"})
    key = reg.json()["api_key"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.api_key == key))
        ev = MarketEvent(
            source="test-trade", source_id="past-close", question="Already closed?",
            category="other", active=True, yes_price=0.5, outcome=None,
            close_time=datetime.now(UTC) - timedelta(hours=1),
        )
        db.add(ev)
        db.commit()
        with pytest.raises(TradeError):
            execute_trade(db, user, ev, "yes", "buy", 10)


def test_settle_resolved_pays_outcome_set_without_settle(client):
    """sync_active can record an outcome without settling; settle_resolved must
    still pay the winners (the orphaned-payout black hole)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User
    from app.trading import execute_trade, settle_resolved

    reg = client.post("/api/users", json={"email": "orphan-winner@example.com"})
    key = reg.json()["api_key"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.api_key == key))
        ev = _make_active_event(db, price=0.25, source_id="orphan-settle")
        execute_trade(db, user, ev, "yes", "buy", 100)  # ⓥ25 for 100 YES
        db.refresh(user)
        pre = user.balance
        # Simulate sync_active's close branch: outcome set, NO settle call.
        ev.outcome = 1
        ev.active = False
        db.commit()
        paid = settle_resolved(db)
        db.refresh(user)
        assert paid >= 1
        assert user.balance == pytest.approx(pre + 100.0)  # ⓥ1/share payout
        # Idempotent — a second sweep pays nothing more.
        assert settle_resolved(db) == 0
