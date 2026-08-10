"""vanta's autonomous play-money agent-traders.

Three deterministic strategies put ⓥ credits behind the forecasting pipeline's
own edge: for every active real-venue market, the pipeline is run once (numbers
only — narratives off, so no LLM ever touches a trade) and each strategy decides
whether the forecast disagrees with the market enough to bet, then trades
through the exact same engine humans do (``app.trading.execute_trade``).

Play money · paper trading · real market prices — ⓥ credits are virtual and
non-redeemable; nothing here moves real money. Probabilities and prices come
from deterministic code only; this module never computes one, it only reads
``forecast.probability`` / ``forecast.confidence`` off the real pipeline and
sizes a stake.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .agents.base import QuestionContext
from .agents.orchestrator import run_pipeline
from .backtest import liquidity_for_volume
from .models import AgentTrader, MarketEvent, Position, Trade, User, utcnow
from .service import learned_base_rate
from .trading import STARTING_BALANCE, TradeError, exec_price, execute_trade, trader_leaderboard

# The three strategies, as data. Each is one deterministic rule over a single
# pipeline run; `threshold` is the one knob that rule turns.
#   edge       — trade the side vanta favors when |forecast - price| >= 0.08
#   confidence — same favored side, but only when pipeline confidence >= 7
#                (stake scales with confidence)
#   contrarian — fade the crowd: buy the side the market prices LOW (< 0.50)
#                only when vanta agrees that cheap side is underpriced by >= 0.10
AGENTS: list[dict] = [
    {"name": "vanta-edge", "strategy": "edge", "threshold": 0.08},
    {"name": "vanta-confidence", "strategy": "confidence", "threshold": 7.0},
    {"name": "vanta-contrarian", "strategy": "contrarian", "threshold": 0.10},
]

# Bots email under a reserved domain so they never collide with human operators.
BOT_EMAIL_DOMAIN = "bots.vanta"

# Fraction of the bot's balance staked per position, before the clamp below.
# 0.01 keeps a fresh bot's stake (ⓥ100 of ⓥ10,000) well inside the band so
# confidence scaling stays visible rather than pinned to the cap.
BANKROLL_FRACTION = 0.01
MIN_STAKE = 1.0
MAX_STAKE = 200.0

# Forecast horizon for a live market = time until it closes. Longer-dated
# markets carry more uncertainty, so the pipeline pulls them harder toward the
# category base rate; near-dated markets stay close to the venue price. A market
# with no stated close (or one already past it) falls back to the default.
DEFAULT_HORIZON_DAYS = 90
MAX_HORIZON_DAYS = 3650


def ensure_agents(db: Session) -> list[AgentTrader]:
    """Create the three bot Users and their AgentTrader rows if missing.

    Idempotent: keyed on AgentTrader.name, so re-running never duplicates a bot
    (and repairs a half-created one — reusing an existing bot User by email).
    Returns the three AgentTrader rows in definition order.
    """
    for spec in AGENTS:
        if db.scalar(select(AgentTrader).where(AgentTrader.name == spec["name"])) is not None:
            continue
        email = f"{spec['name']}@{BOT_EMAIL_DOMAIN}"
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, api_key=f"vk_bot_{uuid.uuid4().hex}")
            db.add(user)
            db.flush()  # assign user.id before the AgentTrader references it
        db.add(AgentTrader(name=spec["name"], strategy=spec["strategy"], user_id=user.id))
    db.commit()
    names = [spec["name"] for spec in AGENTS]
    return db.scalars(
        select(AgentTrader).where(AgentTrader.name.in_(names)).order_by(AgentTrader.id)
    ).all()


def _horizon_days(event: MarketEvent, now: datetime) -> int:
    close = event.close_time
    if close is None:
        return DEFAULT_HORIZON_DAYS
    if close.tzinfo is None:  # SQLite drops tzinfo; naive means UTC here
        close = close.replace(tzinfo=UTC)
    days = (close - now).days
    if days < 1:
        return DEFAULT_HORIZON_DAYS
    return min(days, MAX_HORIZON_DAYS)


def _context_for_event(db: Session, event: MarketEvent, now: datetime) -> QuestionContext:
    """The pipeline context for a live market — built directly (a MarketEvent
    isn't a Question), the same shape the backtest uses: no evidence, no analog
    corpus, narratives off. The learned category base rate is the one DB-derived
    input, via the service helper."""
    volume = event.volume_usd or 0.0
    return QuestionContext(
        question=event.question,
        category=event.category,
        horizon_days=_horizon_days(event, now),
        market_probability=event.yes_price,
        market_volume_usd=volume,
        market_liquidity=liquidity_for_volume(volume),
        evidence=[],
        base_rate=round(learned_base_rate(db, event.category), 4),
        narratives=False,  # numbers only — no LLM call ever fires for a trade
        analog_corpus=[],
    )


def _decide(strategy: str, threshold: float, forecast: float, confidence: float, price: float):
    """Evaluate one strategy against a single pipeline run.

    Returns ``(side, bankroll_fraction)`` when the rule fires (always a BUY —
    the NO side is bought as its own outcome; no shorting), else ``None``.
    """
    edge = forecast - price  # >0: vanta thinks YES underpriced; <0: NO underpriced
    if strategy == "edge":
        if abs(edge) >= threshold:
            return ("yes" if edge > 0 else "no", BANKROLL_FRACTION)
        return None
    if strategy == "confidence":
        # Same favored side as `edge`, gated on confidence instead of magnitude;
        # size scales with how confident the pipeline is.
        if confidence >= threshold and edge != 0:
            return ("yes" if edge > 0 else "no", BANKROLL_FRACTION * (confidence / 10.0))
        return None
    if strategy == "contrarian":
        # The cheap side is whichever the market prices below 0.50. Fire only
        # when vanta puts that cheap side's probability >= threshold above its
        # price — i.e. the crowd underpriced the underdog and vanta agrees.
        if price < 0.5:
            cheap_side, cheap_price, cheap_forecast = "yes", price, forecast
        elif price > 0.5:
            cheap_side, cheap_price, cheap_forecast = "no", 1.0 - price, 1.0 - forecast
        else:
            return None  # perfectly balanced — no side is "the cheap one"
        if cheap_forecast - cheap_price >= threshold:
            return (cheap_side, BANKROLL_FRACTION)
        return None
    return None


def _tradeable_events(db: Session, max_markets: int) -> list[MarketEvent]:
    """Active, unresolved markets with a venue price strictly inside (0, 1),
    the most-traded first and capped at max_markets."""
    stmt = (
        select(MarketEvent)
        .where(
            MarketEvent.active.is_(True),
            MarketEvent.outcome.is_(None),
            MarketEvent.yes_price.is_not(None),
            MarketEvent.yes_price > 0.0,
            MarketEvent.yes_price < 1.0,
        )
        .order_by(MarketEvent.volume_usd.desc(), MarketEvent.id)
        .limit(max_markets)
    )
    return list(db.scalars(stmt).all())


def run_agents_once(db: Session, max_markets: int = 200) -> dict:
    """Run every strategy over the current tradeable markets exactly once.

    For each market the pipeline runs a single time; each bot then evaluates its
    rule against that one forecast and, if it fires and the bot has no position
    on the market yet and can afford the stake, buys through execute_trade.
    Deterministic given the DB (the only clock read is the close-time horizon,
    at day granularity). Returns {evaluated, trades:[{agent, event_id, side,
    shares}]}.
    """
    threshold_of = {spec["strategy"]: spec["threshold"] for spec in AGENTS}
    agents = [
        {"name": a.name, "strategy": a.strategy, "user_id": a.user_id, "threshold": threshold_of[a.strategy]}
        for a in ensure_agents(db)
    ]
    now = utcnow()
    trades: list[dict] = []
    evaluated = 0

    for event in _tradeable_events(db, max_markets):
        price = event.yes_price
        if price is None or not 0.0 < price < 1.0:  # guard against a mid-run reload
            continue
        event_id = event.id
        result = run_pipeline(_context_for_event(db, event, now))
        evaluated += 1

        for agent in agents:
            decision = _decide(
                agent["strategy"], agent["threshold"], result.probability, result.confidence, price
            )
            if decision is None:
                continue
            side, fraction = decision
            # One position per bot per market: never stack, so re-running is a
            # no-op on markets already traded.
            already = db.scalar(
                select(Position.id).where(
                    Position.user_id == agent["user_id"], Position.event_id == event_id
                )
            )
            if already is not None:
                continue
            user = db.get(User, agent["user_id"])
            stake = min(MAX_STAKE, max(MIN_STAKE, fraction * user.balance))
            fill_price = exec_price(event, side)
            shares = stake / fill_price
            try:
                trade = execute_trade(db, user, event, side, "buy", shares, expected_price=fill_price)
            except TradeError:
                # Can't afford it, or the market turned untradeable (past close,
                # price left the band) since selection — skip, stay converged.
                db.rollback()
                continue
            trades.append(
                {"agent": agent["name"], "event_id": event_id, "side": side, "shares": trade.shares}
            )

    return {"evaluated": evaluated, "trades": trades}


def agent_standings(db: Session) -> list[dict]:
    """Every bot's P&L, ranked exactly the way humans are — reusing the trading
    leaderboard's equity / lifetime-P&L math, filtered to the AgentTrader-backed
    users. Bots that have traded appear in leaderboard order (best P&L first);
    bots that haven't yet (absent from the leaderboard) follow, showing their
    flat starting account. Each row carries the bot's strategy."""
    bots = {
        user_id: (name, strategy)
        for user_id, name, strategy in db.execute(
            select(AgentTrader.user_id, AgentTrader.name, AgentTrader.strategy)
        ).all()
    }
    if not bots:
        return []
    n_traders = db.scalar(select(func.count(func.distinct(Trade.user_id)))) or 0
    ranked = trader_leaderboard(db, limit=max(n_traders, 1))  # sorted best-P&L first

    standings: list[dict] = []
    seen: set[int] = set()
    for row in ranked:
        meta = bots.get(row["user_id"])
        if meta is None:
            continue  # a human trader — not a bot
        seen.add(row["user_id"])
        name, strategy = meta
        standings.append(
            {
                "name": name,
                "strategy": strategy,
                "equity": row["equity"],
                "lifetime_pnl": row["lifetime_pnl"],
                "n_trades": row["n_trades"],
            }
        )
    for user_id in sorted(bots):  # bots that never traded — flat starting account
        if user_id in seen:
            continue
        name, strategy = bots[user_id]
        equity = round((db.get(User, user_id).balance) + 0.0, 2)
        standings.append(
            {
                "name": name,
                "strategy": strategy,
                "equity": equity,
                "lifetime_pnl": round(equity - STARTING_BALANCE, 2),
                "n_trades": 0,
            }
        )
    return standings
