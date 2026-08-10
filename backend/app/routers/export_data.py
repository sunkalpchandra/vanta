"""CSV export of a trader's own executions and open/settled positions.

Play-money surface: virtual ⓥ credits at real synced venue prices — never real
money. An export is scoped to exactly one caller: the X-API-Key returned once at
registration IS the trading identity (same `_require_trader` gate the trading
routes use). Deterministic reads only — no LLM, no money math beyond what the
trading engine already computed.
"""

import csv
import io

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent, Position, Trade, User
from ..trading import portfolio

router = APIRouter(prefix="/api/export", tags=["markets"])


def _require_trader(db: Session, x_api_key: str | None) -> User:
    """An export always belongs to exactly one registered trader — same
    identity gate as the trading routes (markets._require_trader)."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    user = db.scalar(select(User).where(User.api_key == x_api_key))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return user


def _csv_response(rows: list[list], header: list[str], filename: str) -> Response:
    """Serialize rows to CSV via the stdlib writer (correct quoting/escaping of
    commas, quotes, newlines) and return it as a downloadable attachment."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trades.csv")
def trades_csv(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Every one of the caller's executions, newest first, as CSV — the
    append-only trade log for spreadsheets and notebooks."""
    user = _require_trader(db, x_api_key)
    rows = db.execute(
        select(Trade, MarketEvent.question)
        .join(MarketEvent, Trade.event_id == MarketEvent.id)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
    ).all()
    data = [
        [
            trade.id,
            # SQLite drops tzinfo despite DateTime(timezone=True); append Z when
            # naive so the stamp reads as UTC (same defense as portfolio/me).
            trade.created_at.isoformat() + ("" if trade.created_at.tzinfo else "Z"),
            trade.event_id,
            question,
            trade.side,
            trade.action,
            trade.shares,
            trade.price,
            trade.cost,
        ]
        for trade, question in rows
    ]
    header = ["id", "created_at", "event_id", "question", "side", "action", "shares", "price", "cost"]
    return _csv_response(data, header, "vanta-trades.csv")


@router.get("/positions.csv")
def positions_csv(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The caller's book — every open and settled position — as CSV, marked to
    current prices by the trading engine (the same view as portfolio/me)."""
    user = _require_trader(db, x_api_key)
    # realized P&L is a stored column the mark-to-market portfolio view omits;
    # pull it per (event, side) — the pair is unique per user (Position index).
    realized = {
        (p.event_id, p.side): p.realized_pnl
        for p in db.scalars(select(Position).where(Position.user_id == user.id)).all()
    }
    book = portfolio(db, user)
    data = [
        [
            p["event_id"],
            p["question"],
            p["side"],
            p["shares"],
            p["avg_price"],
            "" if p["current_price"] is None else p["current_price"],
            p["unrealized_pnl"],
            realized.get((p["event_id"], p["side"]), 0.0),
            p["settled"],
        ]
        for p in book["positions"]
    ]
    header = [
        "event_id",
        "question",
        "side",
        "shares",
        "avg_price",
        "current_price",
        "unrealized_pnl",
        "realized_pnl",
        "settled",
    ]
    return _csv_response(data, header, "vanta-positions.csv")
