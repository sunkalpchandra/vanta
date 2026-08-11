"""compute_stats over a trader's settled positions + trade log.

Shares the suite SQLite (conftest binds it before app import). Every assertion
is scoped to a freshly registered user and this module's own events
(source 'test-w9-stats'); the stats are per-user, so other modules' writes never
matter. Trades go through the real engine (register -> buy -> settle) so the
numbers are exactly what a live book would carry.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent, User
from app.trader_stats import compute_stats
from app.trading import settle_event


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _make_event(yes_price: float = 0.4, question: str | None = None) -> int:
    with SessionLocal() as db:
        event = MarketEvent(
            source="test-w9-stats",
            source_id=f"w9s-{uuid.uuid4().hex}",
            question=question or f"Will stats probe {uuid.uuid4().hex[:8]} resolve YES?",
            category="technology",
            active=True,
            yes_price=yes_price,
            outcome=None,
        )
        db.add(event)
        db.commit()
        return event.id


def _trade(client, user, event_id, side, action, shares):
    return client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers={"X-API-Key": user["api_key"]},
    )


def _settle(event_id: int, outcome: int) -> None:
    with SessionLocal() as db:
        event = db.get(MarketEvent, event_id)
        event.outcome = outcome
        event.active = False
        db.commit()
        settle_event(db, event)


def _stats(user) -> dict:
    with SessionLocal() as db:
        return compute_stats(db, db.get(User, user["id"]))


def test_single_settled_win(client):
    # Buy 100 YES @ ⓥ0.40 (cost ⓥ40), YES resolves -> realized +ⓥ60.
    user = _register(client, "w9-win")
    q = f"Will win probe {uuid.uuid4().hex[:8]} happen?"
    event_id = _make_event(yes_price=0.4, question=q)
    assert _trade(client, user, event_id, "yes", "buy", 100).status_code == 200
    _settle(event_id, outcome=1)

    s = _stats(user)
    assert s["n_settled"] == 1
    assert s["n_wins"] == 1
    assert s["n_losses"] == 0
    assert s["win_rate"] == pytest.approx(1.0)
    assert s["total_realized"] == pytest.approx(60.0)  # 100 * (1.0 - 0.4)
    # Only one settled position -> it is both best and worst.
    assert s["best_trade"]["question"] == q
    assert s["best_trade"]["realized_pnl"] == pytest.approx(60.0)
    assert s["worst_trade"]["question"] == q
    assert s["worst_trade"]["realized_pnl"] == pytest.approx(60.0)
    assert s["n_trades"] == 1  # the single buy (settlement logs no Trade row)
    assert s["n_markets"] == 1
    assert s["avg_trade_size"] == pytest.approx(40.0)  # |cost| of 100 @ 0.40


def test_win_and_loss_record(client):
    # A winner (+60) and a loser (-60) net to zero realized; best/worst split.
    user = _register(client, "w9-mixed")
    win_q = f"Will mixed win {uuid.uuid4().hex[:8]}?"
    lose_q = f"Will mixed lose {uuid.uuid4().hex[:8]}?"
    win_ev = _make_event(yes_price=0.4, question=win_q)
    lose_ev = _make_event(yes_price=0.4, question=lose_q)
    assert _trade(client, user, win_ev, "yes", "buy", 100).status_code == 200  # cost ⓥ40
    assert _trade(client, user, lose_ev, "no", "buy", 100).status_code == 200  # NO @0.6 -> cost ⓥ60
    _settle(win_ev, outcome=1)   # YES wins  -> +60
    _settle(lose_ev, outcome=1)  # NO loses  -> -60

    s = _stats(user)
    assert s["n_settled"] == 2
    assert s["n_wins"] == 1
    assert s["n_losses"] == 1
    assert s["win_rate"] == pytest.approx(0.5)
    assert s["total_realized"] == pytest.approx(0.0)
    assert s["best_trade"]["question"] == win_q
    assert s["best_trade"]["realized_pnl"] == pytest.approx(60.0)
    assert s["worst_trade"]["question"] == lose_q
    assert s["worst_trade"]["realized_pnl"] == pytest.approx(-60.0)
    assert s["n_trades"] == 2
    assert s["n_markets"] == 2
    assert s["avg_trade_size"] == pytest.approx(50.0)  # (|−40| + |−60|) / 2


def test_open_only_book_has_null_win_rate(client):
    # An unsettled open position never enters the outcome stats, but its buy
    # still counts as activity.
    user = _register(client, "w9-open")
    event_id = _make_event(yes_price=0.4)
    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200

    s = _stats(user)
    assert s["n_settled"] == 0
    assert s["n_wins"] == 0
    assert s["n_losses"] == 0
    assert s["win_rate"] is None
    assert s["best_trade"] is None
    assert s["worst_trade"] is None
    assert s["total_realized"] == pytest.approx(0.0)
    assert s["n_trades"] == 1
    assert s["n_markets"] == 1
    assert s["avg_trade_size"] == pytest.approx(4.0)  # |cost| of 10 @ 0.40


def test_untraded_user_is_all_zero(client):
    # Guards the empty-trade-log path (no division by zero on avg_trade_size).
    user = _register(client, "w9-idle")
    s = _stats(user)
    assert s["n_trades"] == 0
    assert s["n_markets"] == 0
    assert s["n_settled"] == 0
    assert s["win_rate"] is None
    assert s["total_realized"] == pytest.approx(0.0)
    assert s["avg_trade_size"] == pytest.approx(0.0)
