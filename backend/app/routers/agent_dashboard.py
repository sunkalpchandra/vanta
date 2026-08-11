"""Agent-trader performance dashboard — how vanta's play-money bots are doing.

Read-only and open (no identity): surfaces each of vanta's autonomous
agent-traders with its live standing — equity, lifetime P&L, open positions,
cash balance, and trade count. Every figure is marked straight through
app.trading.portfolio; nothing is recomputed here.

Play money only — virtual ⓥ credits, paper trading at real synced venue
prices, never real money. The bots put credits behind the deterministic
pipeline's OWN forecasts (numbers only — no LLM ever touches a trade), so their
P&L is the forecasting edge tested honestly: near-zero edge means they mostly
track the market.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentTrader, Trade, User
from ..trading import STARTING_BALANCE, portfolio

router = APIRouter(prefix="/api/agent-traders", tags=["agents"])


class AgentTraderStanding(BaseModel):
    name: str
    strategy: str  # edge | confidence | contrarian
    equity: float  # cash balance + market value of open positions
    lifetime_pnl: float  # equity above the ⓥ10,000 starting bankroll
    n_trades: int
    n_positions: int  # open (unsettled, still-held) positions
    balance: float  # uninvested cash


@router.get("", response_model=list[AgentTraderStanding])
def agent_traders(db: Session = Depends(get_db)) -> list[AgentTraderStanding]:
    """Every vanta agent-trader with its live standing, in creation order.

    Reads the bots straight from the AgentTrader table and marks each book with
    app.trading.portfolio — the same equity/P&L definition the human trader
    leaderboard uses. Nothing is seeded on read, so the list is empty until the
    bots have been created (honest). Deterministic given the DB.
    """
    bots = db.scalars(select(AgentTrader).order_by(AgentTrader.id)).all()
    standings: list[AgentTraderStanding] = []
    for bot in bots:
        user = db.get(User, bot.user_id)
        if user is None:  # half-created bot (no backing User) — skip, never 500
            continue
        book = portfolio(db, user)
        n_open = sum(1 for p in book["positions"] if not p["settled"] and p["shares"] > 0)
        n_trades = db.scalar(select(func.count(Trade.id)).where(Trade.user_id == user.id)) or 0
        standings.append(
            AgentTraderStanding(
                name=bot.name,
                strategy=bot.strategy,
                equity=book["equity"],
                # `+ 0.0` normalizes -0.0 so a flat book never serializes "-0.0".
                lifetime_pnl=round(book["equity"] - STARTING_BALANCE, 2) + 0.0,
                n_trades=int(n_trades),
                n_positions=n_open,
                balance=book["balance"],
            )
        )
    return standings
