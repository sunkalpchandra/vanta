"""Portfolio equity-over-time read API — the caller's realized cash from
trading, reconstructed from the append-only Trade log.

play money · paper trading · real market prices — never real money.

HONEST SCOPE — read this before assuming the series is "equity" or "balance":
this endpoint returns *cash flow from trades* only. It starts at the
STARTING_BALANCE every trader is granted, then applies each trade's signed
`cost` in execution order (a buy debits, a sell credits). It deliberately does
NOT include settlement payouts: settlement credits a winning position's balance
directly (see `trading.settle_event`) WITHOUT writing a Trade row, so this
reconstructed number is intentionally NOT the account balance and NOT
mark-to-market equity. It is the simple, exactly-correct thing the trade log
alone can prove — kept honest rather than faking a full equity curve.
"""

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Trade
from ..schemas import UTCDateTime
from ..trading import STARTING_BALANCE
from .markets import _require_trader

router = APIRouter(prefix="/api/portfolio", tags=["markets"])

# Surfaced verbatim in the response so any UI reading this can't mislabel it.
BASIS = "cash flow from trades (buys debit, sells credit); excludes settlement payouts"


def _money(amount: float) -> float:
    # 2dp at the boundary; `+ 0.0` normalizes -0.0 so serialized cash is clean.
    return round(amount, 2) + 0.0


class EquityPoint(BaseModel):
    timestamp: UTCDateTime
    cash: float


class EquityHistoryOut(BaseModel):
    points: list[EquityPoint]
    starting_balance: float
    basis: str = BASIS


@router.get("/equity", response_model=EquityHistoryOut)
def portfolio_equity(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The caller's realized cash from trading over time, oldest-first.

    Walks the trade log applying each signed `cost` and emits a point after
    every fill, prepended by an opening point that holds the full
    STARTING_BALANCE. See the module docstring: this is *cash flow from
    trades*, not the account balance and not mark-to-market equity —
    settlement payouts credit the balance directly (no Trade row) and are
    excluded. X-API-Key required (401 without a valid trading identity).
    """
    user = _require_trader(db, x_api_key)
    trades = db.scalars(
        select(Trade)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.asc(), Trade.id.asc())
    ).all()

    # Opening point: the account began with the full grant. Anchor it at the
    # account's creation time — a trader always registers before trading, so
    # this precedes the first fill and the series opens flat at STARTING_BALANCE
    # and stays non-decreasing in time. (Guard against clock skew defensively.)
    opening_ts = user.created_at
    if trades and trades[0].created_at < opening_ts:
        opening_ts = trades[0].created_at

    points = [EquityPoint(timestamp=opening_ts, cash=_money(STARTING_BALANCE))]
    cash = STARTING_BALANCE
    for trade in trades:
        cash += trade.cost  # signed balance delta: buy negative, sell positive
        points.append(EquityPoint(timestamp=trade.created_at, cash=_money(cash)))

    return EquityHistoryOut(points=points, starting_balance=_money(STARTING_BALANCE))
