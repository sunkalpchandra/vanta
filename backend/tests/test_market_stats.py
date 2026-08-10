"""Market-surface stats + biggest-movers API.

Shares the suite SQLite (conftest binds it before app import). The stats
endpoints are GLOBAL aggregates, so assertions use before/after DELTAS (never
absolute totals — other modules write into the same corpus) and scope fixture
rows to a unique source ('test-w8-mstats') except where a real venue name is
required to exercise the per-source breakdown.

Until main.py wires the market-stats router (a shared file, handled in the
integration step), mount it here — a guarded no-op once main.py includes it.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import MarketEvent, PriceTick


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_event(
    *,
    source: str = "test-w8-mstats",
    active: bool = True,
    outcome: int | None = None,
    yes_price: float | None = 0.5,
    volume: float = 0.0,
) -> int:
    with SessionLocal() as db:
        ev = MarketEvent(
            source=source,
            source_id=f"w8m-{uuid.uuid4().hex}",
            question=f"Will mstats probe {uuid.uuid4().hex[:6]} resolve YES?",
            category="technology",
            active=active,
            outcome=outcome,
            yes_price=yes_price,
            volume_usd=volume,
        )
        db.add(ev)
        db.commit()
        return ev.id


def _add_tick(event_id: int, yes_price: float, *, hours_ago: float) -> None:
    """Insert a PriceTick at a controlled age (bypassing record_tick's dedupe)."""
    with SessionLocal() as db:
        tick = PriceTick(event_id=event_id, yes_price=yes_price)
        db.add(tick)
        db.commit()
        tick.timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
        db.commit()


def _register(client, tag: str) -> dict:
    resp = client.post("/api/users", json={"email": f"{tag}-{uuid.uuid4().hex[:8]}@vanta.test"})
    assert resp.status_code == 201
    return resp.json()


def _trade(client, user, event_id, side, action, shares):
    return client.post(
        f"/api/markets/{event_id}/trade",
        json={"side": side, "action": action, "shares": shares},
        headers={"X-API-Key": user["api_key"]},
    )


def _stats(client) -> dict:
    resp = client.get("/api/market-stats")
    assert resp.status_code == 200
    return resp.json()


def _movers(client, **params) -> list[dict]:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    resp = client.get(f"/api/market-stats/movers?{query}" if query else "/api/market-stats/movers")
    assert resp.status_code == 200
    return resp.json()


# --- route safety: the /{event_id} collision this prefix sidesteps -------------


def test_market_stats_avoids_event_id_collision(client):
    """`/api/markets/stats` and `/api/markets/movers` are single-segment paths
    that markets.router parses as an int `{event_id}` (registered ahead of us),
    so they 422 before any stats handler — which is exactly why this router
    lives under the distinct, collision-proof `/api/market-stats` prefix."""
    assert client.get("/api/markets/stats").status_code == 422
    assert client.get("/api/markets/movers").status_code == 422

    resp = client.get("/api/market-stats")
    assert resp.status_code == 200
    body = resp.json()
    assert {
        "n_active",
        "n_settled",
        "by_source",
        "total_volume_usd",
        "n_traders",
        "n_open_positions",
        "n_trades",
    } <= set(body.keys())
    assert set(body["by_source"].keys()) == {"polymarket", "kalshi", "manifold"}


# --- stats aggregates ----------------------------------------------------------


def test_stats_counts_move_with_new_rows(client):
    before = _stats(client)

    _make_event(source="polymarket", active=True, yes_price=0.4, volume=100.0)
    _make_event(source="kalshi", active=True, yes_price=0.6, volume=250.0)
    _make_event(source="manifold", active=True, yes_price=0.3, volume=50.0)
    # Settled + inactive: bumps n_settled and total_volume, but NOT n_active or
    # the active-only by_source breakdown.
    _make_event(source="polymarket", active=False, outcome=1, yes_price=0.9, volume=10.0)

    after = _stats(client)

    assert after["n_active"] - before["n_active"] == 3
    assert after["n_settled"] - before["n_settled"] == 1
    assert after["by_source"]["polymarket"] - before["by_source"]["polymarket"] == 1  # active one only
    assert after["by_source"]["kalshi"] - before["by_source"]["kalshi"] == 1
    assert after["by_source"]["manifold"] - before["by_source"]["manifold"] == 1
    # total_volume_usd sums the WHOLE corpus, settled included: 100+250+50+10.
    assert round(after["total_volume_usd"] - before["total_volume_usd"], 2) == 410.0


def test_stats_reflects_first_trade_and_open_position(client):
    before = _stats(client)
    user = _register(client, "mstats")
    event_id = _make_event(active=True, yes_price=0.4)

    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200

    after = _stats(client)
    assert after["n_traders"] - before["n_traders"] == 1  # a brand-new participant
    assert after["n_open_positions"] - before["n_open_positions"] == 1
    assert after["n_trades"] - before["n_trades"] == 1


def test_fully_sold_position_is_not_counted_open(client):
    user = _register(client, "mstats-exit")
    event_id = _make_event(active=True, yes_price=0.4)
    assert _trade(client, user, event_id, "yes", "buy", 10).status_code == 200
    mid = _stats(client)

    assert _trade(client, user, event_id, "yes", "sell", 10).status_code == 200
    after = _stats(client)

    # Position row survives (carries realized P&L) but shares -> 0, so the
    # shares>0 guard drops it from the open count. The sell is still a trade.
    assert after["n_open_positions"] == mid["n_open_positions"] - 1
    assert after["n_trades"] == mid["n_trades"] + 1
    assert after["n_traders"] == mid["n_traders"]  # same trader, no new participant


# --- movers --------------------------------------------------------------------


def test_movers_ranks_by_absolute_change(client):
    big_down = _make_event(active=True, yes_price=0.20, volume=400.0)
    _add_tick(big_down, 0.60, hours_ago=10)  # change -0.40

    big_up = _make_event(active=True, yes_price=0.80, volume=500.0)
    _add_tick(big_up, 0.50, hours_ago=10)  # change +0.30

    mid = _make_event(active=True, yes_price=0.55, volume=300.0)
    _add_tick(mid, 0.40, hours_ago=10)  # change +0.15

    body = _movers(client, window_hours=24, limit=100)
    mine = {m["event_id"]: m for m in body if m["event_id"] in {big_down, big_up, mid}}
    assert set(mine) == {big_down, big_up, mid}

    # prev = earliest-in-window price; yes_price = current; change = signed.
    assert mine[big_up]["prev_price"] == pytest.approx(0.50)
    assert mine[big_up]["yes_price"] == pytest.approx(0.80)
    assert mine[big_up]["source"] == "test-w8-mstats"
    assert mine[big_up]["volume_usd"] == pytest.approx(500.0)
    assert mine[big_up]["change"] == pytest.approx(0.30)
    assert mine[big_down]["change"] == pytest.approx(-0.40)
    assert mine[mid]["change"] == pytest.approx(0.15)

    # Biggest |change| first: relative order of ours must be down(.40) < up(.30) < mid(.15).
    order = [m["event_id"] for m in body if m["event_id"] in mine]
    assert order == [big_down, big_up, mid]


def test_movers_uses_earliest_in_window_tick(client):
    ev = _make_event(active=True, yes_price=0.90)
    _add_tick(ev, 0.40, hours_ago=20)  # earliest in-window reference
    _add_tick(ev, 0.70, hours_ago=5)  # a later in-window tick — must be ignored

    m = next((x for x in _movers(client, window_hours=24, limit=100) if x["event_id"] == ev), None)
    assert m is not None
    assert m["prev_price"] == pytest.approx(0.40)  # earliest, not 0.70
    assert m["change"] == pytest.approx(0.50)  # 0.90 - 0.40


def test_movers_excludes_inactive_no_tick_and_out_of_window(client):
    active_no_tick = _make_event(active=True, yes_price=0.7)  # never ticked
    inactive_with_tick = _make_event(active=False, yes_price=0.7)
    _add_tick(inactive_with_tick, 0.3, hours_ago=5)  # big move, but not tradeable
    old_tick_only = _make_event(active=True, yes_price=0.7)
    _add_tick(old_tick_only, 0.3, hours_ago=48)  # sole tick predates a 24h window

    ids = {m["event_id"] for m in _movers(client, window_hours=24, limit=100)}
    assert active_no_tick not in ids
    assert inactive_with_tick not in ids
    assert old_tick_only not in ids


def test_wider_window_pulls_in_older_reference_tick(client):
    ev = _make_event(active=True, yes_price=0.65)
    _add_tick(ev, 0.35, hours_ago=48)  # 48h old

    assert ev not in {m["event_id"] for m in _movers(client, window_hours=24, limit=100)}

    m = next((x for x in _movers(client, window_hours=72, limit=100) if x["event_id"] == ev), None)
    assert m is not None
    assert m["prev_price"] == pytest.approx(0.35)
    assert m["change"] == pytest.approx(0.30)  # 0.65 - 0.35


def test_movers_limit_and_validation(client):
    assert len(_movers(client, limit=1)) <= 1
    assert client.get("/api/market-stats/movers?limit=0").status_code == 422
    assert client.get("/api/market-stats/movers?limit=101").status_code == 422
    assert client.get("/api/market-stats/movers?window_hours=0").status_code == 422
    assert client.get("/api/market-stats/movers?window_hours=-5").status_code == 422
