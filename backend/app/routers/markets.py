"""Play-money market trading API — virtual ⓥ credits at real synced venue prices.

play money · paper trading · real market prices — never real money. Reads are
open; anything touching a balance requires the X-API-Key returned once at
registration (POST /api/users) as trading identity.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent, Position, Trade, User
from ..schemas import UTCDateTime
from ..trading import TradeError, execute_trade, portfolio, trader_leaderboard

router = APIRouter(prefix="/api/markets", tags=["markets"])

DISCLAIMER = "play money · paper trading · real market prices"


class MarketItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    category: str
    source: str
    yes_price: float | None
    volume_usd: float
    close_time: UTCDateTime | None
    outcome: int | None


class MarketList(BaseModel):
    total: int
    items: list[MarketItem]
    note: str = DISCLAIMER


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    side: str
    shares: float
    avg_price: float
    realized_pnl: float
    settled: bool


class MarketDetail(MarketItem):
    active: bool
    no_price: float | None
    last_synced: UTCDateTime | None
    my_positions: list[PositionOut] = []
    note: str = DISCLAIMER


class TradeRequest(BaseModel):
    side: Literal["yes", "no"]
    action: Literal["buy", "sell"]
    shares: float = Field(gt=0, le=1_000_000_000)
    # The price the UI showed the trader. If the synced price has moved beyond
    # SLIPPAGE_TOLERANCE by execution time, the fill is rejected (409) rather
    # than silently filled at the new price.
    expected_price: float | None = Field(default=None, gt=0, lt=1)


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    side: str
    action: str
    shares: float
    price: float
    cost: float  # signed balance delta (negative = credits spent)
    created_at: UTCDateTime


class TradeResponse(BaseModel):
    trade: TradeOut
    balance: float
    position: PositionOut
    note: str = DISCLAIMER


def _require_trader(db: Session, x_api_key: str | None) -> User:
    """Trading always needs an identity, independent of the demo-mode operator
    gate: the balance being moved belongs to exactly one registered user."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key required")
    user = db.scalar(select(User).where(User.api_key == x_api_key))
    if user is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return user


@router.get("", response_model=MarketList)
def list_markets(
    status: Literal["active", "settled"] = "active",
    category: str | None = None,
    q: str | None = None,
    sort: Literal["volume", "close_time"] = "volume",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated tradeable (or settled) real-venue markets."""
    filters = []
    if status == "active":
        filters.append(MarketEvent.active.is_(True))
    else:
        filters.append(MarketEvent.outcome.is_not(None))
    if category:
        filters.append(MarketEvent.category == category)
    if q:
        filters.append(MarketEvent.question.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(MarketEvent).where(*filters)) or 0
    stmt = select(MarketEvent).where(*filters)
    if sort == "volume":
        stmt = stmt.order_by(MarketEvent.volume_usd.desc(), MarketEvent.id)
    else:  # soonest close first; events without a close time sink to the end
        stmt = stmt.order_by(MarketEvent.close_time.is_(None), MarketEvent.close_time.asc(), MarketEvent.id)
    events = db.scalars(stmt.limit(limit).offset(offset)).all()
    return MarketList(total=total, items=[MarketItem.model_validate(e) for e in events])


@router.get("/traders")
def traders(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Play-money leaderboard: lifetime P&L vs the ⓥ10,000 everyone starts with."""
    return {"traders": trader_leaderboard(db, limit=limit), "note": DISCLAIMER}


@router.get("/portfolio/me")
def my_portfolio(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The caller's balance, positions marked to current prices, equity, and
    the most recent executions (the UI's trade history)."""
    user = _require_trader(db, x_api_key)
    recent = db.execute(
        select(Trade, MarketEvent.question)
        .join(MarketEvent, Trade.event_id == MarketEvent.id)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .limit(25)
    ).all()
    recent_trades = [
        {
            "id": trade.id,
            "event_id": trade.event_id,
            "question": question,
            "side": trade.side,
            "action": trade.action,
            "shares": trade.shares,
            "price": trade.price,
            "cost": trade.cost,
            "created_at": trade.created_at.isoformat() + ("" if trade.created_at.tzinfo else "Z"),
        }
        for trade, question in recent
    ]
    return {**portfolio(db, user), "recent_trades": recent_trades, "note": DISCLAIMER}


@router.post("/{event_id}/trade", response_model=TradeResponse)
def place_trade(
    event_id: int,
    body: TradeRequest,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Buy or sell play-money shares at the current synced venue price."""
    user = _require_trader(db, x_api_key)
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="market not found")
    try:
        trade = execute_trade(
            db, user, event, body.side, body.action, body.shares, expected_price=body.expected_price
        )
    except TradeError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    position = db.scalar(
        select(Position).where(
            Position.user_id == user.id,
            Position.event_id == event.id,
            Position.side == body.side,
        )
    )
    return TradeResponse(
        trade=TradeOut.model_validate(trade),
        balance=round(user.balance, 2),
        position=PositionOut.model_validate(position),
    )


@router.get("/{event_id}", response_model=MarketDetail)
def market_detail(
    event_id: int,
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Event detail; with a valid X-API-Key it also includes the caller's
    positions on this event (an invalid or missing key just omits them)."""
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="market not found")
    detail = MarketDetail(
        id=event.id,
        question=event.question,
        category=event.category,
        source=event.source,
        yes_price=event.yes_price,
        volume_usd=event.volume_usd,
        close_time=event.close_time,
        outcome=event.outcome,
        active=event.active,
        no_price=round(1.0 - event.yes_price, 6) if event.yes_price is not None else None,
        last_synced=event.last_synced,
    )
    if x_api_key:
        user = db.scalar(select(User).where(User.api_key == x_api_key))
        if user is not None:
            mine = db.scalars(select(Position).where(Position.user_id == user.id, Position.event_id == event.id)).all()
            detail.my_positions = [PositionOut.model_validate(p) for p in mine]
    return detail
