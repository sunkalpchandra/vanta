"""Public trader profiles — a per-trader view of the play-money book.

Read-only and open (no identity needed): resolves a trader by the same email
LOCAL-PART shown everywhere else (leaderboard, activity tape) and returns their
balance, equity, realized P&L, positions marked to current venue prices, and
recent executions. Play money only — virtual ⓥ credits, paper trading at real
synced venue prices, never real money.

Privacy: a trader is addressed and displayed by their email local-part only;
the full registration email and the api_key never leave this endpoint — the
same redaction rule the leaderboard and activity tape follow. Nothing here
recomputes a price or a balance: figures come straight from app.trading.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent, Trade, User
from ..trading import portfolio, trader_leaderboard

router = APIRouter(prefix="/api/traders", tags=["markets"])

DISCLAIMER = "play money · paper trading · real market prices"


def _handle(email: str) -> str:
    """The public display handle: the email local-part, never the full email."""
    return email.split("@")[0]


@router.get("")
def traders(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Play-money leaderboard, mirroring /api/markets/traders so the profiles
    surface has one clean list to page through and link from."""
    return {"traders": trader_leaderboard(db, limit=limit), "note": DISCLAIMER}


@router.get("/{name}")
def trader_profile(name: str, db: Session = Depends(get_db)):
    """One trader's public book, addressed by email local-part. 404 when no
    registered trader owns that handle."""
    # Exact prefix match with LIKE wildcards ESCAPED — an unescaped name like
    # "%" would otherwise force a full users-table scan (and match everyone).
    escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    candidates = db.scalars(
        select(User).where(User.email.like(f"{escaped}@%", escape="\\")).order_by(User.id)
    ).all()
    user = next((u for u in candidates if _handle(u.email) == name), None)
    if user is None:
        raise HTTPException(status_code=404, detail="trader not found")

    n_trades = db.scalar(select(func.count(Trade.id)).where(Trade.user_id == user.id)) or 0
    # Only traders who have actually traded have a public profile — otherwise
    # the endpoint would let anyone enumerate registered handles and read their
    # starting balances by guessing email local-parts.
    if not n_trades:
        raise HTTPException(status_code=404, detail="trader not found")

    book = portfolio(db, user)
    recent = db.execute(
        select(Trade, MarketEvent.question)
        .join(MarketEvent, Trade.event_id == MarketEvent.id)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .limit(25)
    ).all()
    recent_trades = [
        {
            "event_id": trade.event_id,
            "question": question,
            "side": trade.side,
            "action": trade.action,
            "shares": trade.shares,
            "price": trade.price,
            # SQLite drops tzinfo despite DateTime(timezone=True); append Z so
            # the browser parses UTC (same defense as the activity tape).
            "created_at": trade.created_at.isoformat() + ("" if trade.created_at.tzinfo else "Z"),
        }
        for trade, question in recent
    ]
    return {
        "name": _handle(user.email),
        "joined": user.created_at.isoformat() + ("" if user.created_at.tzinfo else "Z"),
        "balance": book["balance"],
        "equity": book["equity"],
        "realized_pnl": book["realized_pnl_total"],
        "n_trades": int(n_trades),
        "positions": book["positions"],
        "recent_trades": recent_trades,
        "note": DISCLAIMER,
    }
