"""Public activity tape — the live play-money trade feed across all traders.

Read-only and open (no identity): it surfaces recent executions for the
homepage/markets strip. Play money only — virtual ⓥ credits, paper trading at
real synced venue prices, never real money. Prices/amounts are copied straight
from the append-only Trade log written by app.trading; nothing is recomputed
here.

Privacy: a trader is shown by their agent name (bot traders) or their email
LOCAL-PART only — a full registration email never leaves this endpoint, the
same rule the trader leaderboard follows.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentTrader, MarketEvent, Trade, User

router = APIRouter(prefix="/api/activity", tags=["activity"])

DISCLAIMER = "play money · paper trading · real market prices"


@router.get("/trades")
def recent_trades(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    """Most recent trades across every trader, newest first, joined to the
    market question and a display handle. Envelope carries the play-money note."""
    rows = db.execute(
        select(Trade, User.email, MarketEvent.question, AgentTrader.name)
        .join(User, Trade.user_id == User.id)
        .join(MarketEvent, Trade.event_id == MarketEvent.id)
        # A bot trader is backed by a User AND an AgentTrader; humans have no
        # AgentTrader row, so this stays an outer join (name -> None).
        .outerjoin(AgentTrader, AgentTrader.user_id == User.id)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .limit(limit)
    ).all()
    trades = [
        {
            "id": trade.id,
            # Agent name when it's a bot, else the email local-part — never the
            # full email (redaction; matches trader_leaderboard).
            "trader": agent_name or email.split("@")[0],
            "event_id": trade.event_id,
            "question": question,
            "side": trade.side,
            "action": trade.action,
            "shares": trade.shares,
            "price": trade.price,
            # SQLite drops tzinfo despite DateTime(timezone=True); append Z so
            # the browser parses it as UTC (same defense as portfolio/me).
            "created_at": trade.created_at.isoformat() + ("" if trade.created_at.tzinfo else "Z"),
        }
        for trade, email, question, agent_name in rows
    ]
    return {"trades": trades, "note": DISCLAIMER}
