"""Play-money trading engine over real synced venue prices.

Everything here moves virtual ⓥ credits only — paper trading against real
Polymarket/Kalshi prices, never real money. Deterministic code: no LLM ever
touches a number in this module.

Money conventions (enforced at the boundaries):
- amounts that hit a balance (cost, proceeds, payouts, realized P&L) are
  rounded to 2 decimals; execution prices are probabilities kept at 6 decimals
  so NO-side complements (1 - yes_price) don't accumulate float noise.
- balances can never go negative; sells are capped at held shares.

Business rejections raise TradeError, which the API layer maps to HTTP 409.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import MarketEvent, Position, Trade, User, utcnow

STARTING_BALANCE = 10_000.0

# Below this, a buy's cost would round to ⓥ0.00 — free shares. Reject.
MIN_NOTIONAL = 0.01


class TradeError(Exception):
    """A business-rule rejection (insufficient balance, inactive event, ...)."""


def _round_money(amount: float) -> float:
    # `+ 0.0` normalizes -0.0 to 0.0 so serialized balances never show "-0.0".
    return round(amount, 2) + 0.0


def exec_price(event: MarketEvent, side: str) -> float:
    """Execution price per share: YES trades at the synced venue YES price,
    NO at its complement. Caller must have validated yes_price."""
    price = event.yes_price if side == "yes" else 1.0 - event.yes_price
    return round(price, 6)


def _validate_tradeable(event: MarketEvent, side: str, action: str, shares: float) -> None:
    if side not in ("yes", "no"):
        raise TradeError("side must be 'yes' or 'no'")
    if action not in ("buy", "sell"):
        raise TradeError("action must be 'buy' or 'sell'")
    if not shares > 0:  # also False for NaN
        raise TradeError("shares must be greater than 0")
    if event.outcome is not None:
        raise TradeError("event already resolved")
    if not event.active:
        raise TradeError("event is not active for trading")
    if event.yes_price is None:
        raise TradeError("event has no synced price yet")
    if not 0.0 < event.yes_price < 1.0:
        raise TradeError("venue price is outside (0, 1) — not tradeable")


def execute_trade(
    db: Session,
    user: User,
    event: MarketEvent,
    side: str,
    action: str,
    shares: float,
) -> Trade:
    """Execute one play-money buy/sell at the current synced price.

    All mutations (position upsert, balance move, trade log) commit in one
    transaction. Returns the appended Trade row; its `shares` is the executed
    quantity (sells are capped at held shares) and `cost` is the signed
    balance delta (negative = credits spent).
    """
    _validate_tradeable(event, side, action, shares)
    price = exec_price(event, side)

    position = db.scalar(
        select(Position).where(
            Position.user_id == user.id,
            Position.event_id == event.id,
            Position.side == side,
        )
    )
    if position is not None and position.settled:
        raise TradeError("position already settled")

    if action == "buy":
        cost = _round_money(shares * price)
        if cost < MIN_NOTIONAL:
            raise TradeError(f"trade too small — cost must be at least ⓥ{MIN_NOTIONAL:.2f}")
        if cost > user.balance + 1e-9:
            raise TradeError(f"insufficient balance: cost ⓥ{cost:.2f} exceeds ⓥ{user.balance:.2f}")
        if position is None:
            position = Position(user_id=user.id, event_id=event.id, side=side, shares=0.0, avg_price=0.0)
            db.add(position)
        total_shares = position.shares + shares
        position.avg_price = (position.shares * position.avg_price + shares * price) / total_shares
        position.shares = total_shares
        user.balance = _round_money(user.balance - cost)
        executed, delta = shares, -cost
    else:  # sell
        if position is None or position.shares <= 0:
            raise TradeError("no shares to sell")
        executed = min(shares, position.shares)  # cap at held
        proceeds = _round_money(executed * price)
        realized = _round_money(executed * (price - position.avg_price))
        position.shares = round(position.shares - executed, 9)
        if position.shares < 1e-9:
            position.shares = 0.0  # keep the row — it carries realized P&L history
        position.realized_pnl = _round_money(position.realized_pnl + realized)
        user.balance = _round_money(user.balance + proceeds)
        delta = proceeds

    position.updated_at = utcnow()
    trade = Trade(
        user_id=user.id,
        event_id=event.id,
        side=side,
        action=action,
        shares=executed,
        price=price,
        cost=delta,
    )
    db.add(trade)
    db.commit()
    return trade


def settle_event(db: Session, event: MarketEvent) -> int:
    """Pay out every unsettled position on a resolved event: ⓥ1 per share on
    the winning side, ⓥ0 on the losing side. Idempotent — settled positions
    are skipped, so the sync engine may call this on every pass. Returns the
    number of positions settled (0 when nothing was left to do).
    """
    if event.outcome not in (0, 1):
        raise ValueError("settle_event requires a resolved outcome (0 or 1)")
    winning_side = "yes" if event.outcome == 1 else "no"
    positions = db.scalars(select(Position).where(Position.event_id == event.id, Position.settled.is_(False))).all()
    for position in positions:
        payout_per_share = 1.0 if position.side == winning_side else 0.0
        payout = _round_money(position.shares * payout_per_share)
        if payout:
            holder = db.get(User, position.user_id)
            holder.balance = _round_money(holder.balance + payout)
        position.realized_pnl = _round_money(
            position.realized_pnl + position.shares * (payout_per_share - position.avg_price)
        )
        position.settled = True
        position.updated_at = utcnow()
    db.commit()
    return len(positions)


def _mark_price(event: MarketEvent, side: str) -> float | None:
    """Current per-share value of a side: resolution value once the outcome is
    known, else the synced venue price (None when there isn't a valid one)."""
    if event.outcome is not None:
        return 1.0 if (side == "yes") == bool(event.outcome) else 0.0
    if event.yes_price is None or not 0.0 < event.yes_price < 1.0:
        return None
    return exec_price(event, side)


def portfolio(db: Session, user: User) -> dict:
    """Mark-to-market account view: balance, every position (open and settled
    history rows), total realized P&L, and equity = balance + market value of
    open positions — the same definition the trader leaderboard ranks by."""
    rows = db.execute(
        select(Position, MarketEvent)
        .join(MarketEvent, Position.event_id == MarketEvent.id)
        .where(Position.user_id == user.id)
        .order_by(Position.updated_at.desc(), Position.id.desc())
    ).all()

    positions: list[dict] = []
    realized_total = 0.0
    unrealized_total = 0.0
    market_value = 0.0
    for position, event in rows:
        realized_total += position.realized_pnl
        current = _mark_price(event, position.side)
        if position.settled or position.shares <= 0 or current is None:
            unrealized = 0.0
        else:
            unrealized = _round_money(position.shares * (current - position.avg_price))
            market_value += position.shares * current
        unrealized_total += unrealized
        positions.append(
            {
                "event_id": event.id,
                "question": event.question,
                "side": position.side,
                "shares": position.shares,
                "avg_price": position.avg_price,
                "current_price": current,
                "unrealized_pnl": unrealized,
                "settled": position.settled,
            }
        )

    balance = _round_money(user.balance)
    return {
        "balance": balance,
        "positions": positions,
        "realized_pnl_total": _round_money(realized_total),
        "unrealized_pnl_total": _round_money(unrealized_total),
        "equity": _round_money(balance + market_value),
    }


def trader_leaderboard(db: Session, limit: int = 20) -> list[dict]:
    """Traders ranked by lifetime P&L = equity - starting ⓥ10,000, where
    equity marks open positions to current prices (realized P&L already lives
    in the balance). Users who never traded are excluded."""
    trade_counts: dict[int, int] = dict(
        db.execute(select(Trade.user_id, func.count(Trade.id)).group_by(Trade.user_id)).all()
    )
    if not trade_counts:
        return []

    users = db.scalars(select(User).where(User.id.in_(trade_counts))).all()
    open_rows = db.execute(
        select(Position, MarketEvent)
        .join(MarketEvent, Position.event_id == MarketEvent.id)
        .where(
            Position.user_id.in_(trade_counts),
            Position.settled.is_(False),
            Position.shares > 0,
        )
    ).all()

    value_by_user: dict[int, float] = {}
    for position, event in open_rows:
        current = _mark_price(event, position.side)
        if current is None:
            current = position.avg_price  # no synced price — mark at cost basis
        value_by_user[position.user_id] = value_by_user.get(position.user_id, 0.0) + position.shares * current

    rows = []
    for user in users:
        equity = _round_money(user.balance + value_by_user.get(user.id, 0.0))
        rows.append(
            {
                "user_id": user.id,
                # Display handle only — never leak full registration emails.
                "name": user.email.split("@")[0],
                "equity": equity,
                "lifetime_pnl": _round_money(equity - STARTING_BALANCE),
                "n_trades": int(trade_counts.get(user.id, 0)),
            }
        )
    rows.sort(key=lambda r: (-r["lifetime_pnl"], r["user_id"]))
    return rows[:limit]
