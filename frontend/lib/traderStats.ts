// Play-money trader statistics: the shape the trader-profile endpoint embeds
// under `stats`, plus pure display helpers. No fetch here — the profile response
// already carries the stats, and TraderStats.tsx takes them as a prop. Play
// money only: virtual ⓥ credits, paper trading at real synced venue prices,
// never real money.

/** One settled market surfaced as the trader's best / worst result. */
export interface TraderStatTrade {
  question: string;
  realized_pnl: number;
}

/** Mirror of app.trader_stats.compute_stats — embedded in the profile response.
 * win_rate is a 0..1 fraction (null when nothing is decided); best/worst are
 * null when the trader has no settled positions yet. */
export interface TraderStats {
  n_settled: number;
  n_wins: number;
  n_losses: number;
  win_rate: number | null;
  total_realized: number;
  best_trade: TraderStatTrade | null;
  worst_trade: TraderStatTrade | null;
  n_trades: number;
  n_markets: number;
  avg_trade_size: number;
}

// --- pure display helpers (deterministic, unit-tested) ----------------------

/** A 0..1 win-rate fraction as a whole-percent string ("63%"); "—" when the
 * rate is undefined (null / NaN — no decided positions to average). */
export function formatWinRate(x: number | null): string {
  if (x === null || Number.isNaN(x)) return "—";
  return `${Math.round(x * 100)}%`;
}

/** Tone bucket for a signed P&L figure: gains are "pos", losses "neg", and an
 * exactly flat book "flat". Maps to a text color in the component (a three-way
 * split, unlike pnlColor's binary green/red). */
export function pnlTone(n: number): "pos" | "neg" | "flat" {
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "flat";
}
