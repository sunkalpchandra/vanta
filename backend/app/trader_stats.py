"""Richer play-money trader statistics — win rate, record, best/worst market.

Read-only aggregation over a trader's SETTLED positions (settled=True carry the
frozen realized_pnl that trading.settle_event wrote) and their full trade log.
Deterministic: this module never moves a balance or recomputes a price — it only
summarizes what app.trading already recorded, reusing the engine's own money
rounding so figures line up with the portfolio to the cent. Play money only —
virtual ⓥ credits, paper trading at real synced venue prices, never real money.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MarketEvent, Position, Trade, User
from .trading import _round_money


def compute_stats(db: Session, user: User) -> dict:
    """A trader's play-money record, derived from their settled positions and
    trade log.

    Settled positions (the resolved book) drive the outcome stats; a position
    with realized_pnl > 0 is a win, < 0 a loss, and exactly 0 is neither (so it
    counts toward n_settled but not the win rate). The trade log drives the
    activity stats. Keys:

      n_settled       settled positions on this book
      n_wins/n_losses settled positions with realized_pnl >0 / <0
      win_rate        wins / (wins + losses); None when nothing is decided
      total_realized  net realized P&L across the settled book
      best_trade      {question, realized_pnl} of the top settled position
      worst_trade     ... of the bottom settled position (None when none settled)
      n_trades        every logged buy/sell
      n_markets       distinct events the trader has touched
      avg_trade_size  mean |signed cost| over trades (0.0 when none)
    """
    settled = db.execute(
        select(Position, MarketEvent.question)
        .join(MarketEvent, Position.event_id == MarketEvent.id)
        .where(Position.user_id == user.id, Position.settled.is_(True))
    ).all()

    n_settled = len(settled)
    n_wins = sum(1 for position, _ in settled if position.realized_pnl > 0)
    n_losses = sum(1 for position, _ in settled if position.realized_pnl < 0)
    decided = n_wins + n_losses
    win_rate = n_wins / decided if decided else None
    total_realized = _round_money(sum(position.realized_pnl for position, _ in settled))

    best_trade = worst_trade = None
    if settled:
        # Tie-break on position id so equal realized_pnl always resolves to the
        # same row regardless of DB row order — keeps the readout deterministic.
        ranked = sorted(settled, key=lambda row: (row[0].realized_pnl, row[0].id))
        worst_position, worst_question = ranked[0]
        best_position, best_question = ranked[-1]
        best_trade = {"question": best_question, "realized_pnl": _round_money(best_position.realized_pnl)}
        worst_trade = {"question": worst_question, "realized_pnl": _round_money(worst_position.realized_pnl)}

    trades = db.execute(select(Trade.cost, Trade.event_id).where(Trade.user_id == user.id)).all()
    n_trades = len(trades)
    n_markets = len({event_id for _, event_id in trades})
    avg_trade_size = _round_money(sum(abs(cost) for cost, _ in trades) / n_trades) if n_trades else 0.0

    return {
        "n_settled": n_settled,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "win_rate": win_rate,
        "total_realized": total_realized,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "n_trades": n_trades,
        "n_markets": n_markets,
        "avg_trade_size": avg_trade_size,
    }
