// Trade-history data + a pure summary reducer for the play-money market.
// The trade log the backend already returns from the portfolio endpoint IS the
// history feed — reuse it rather than adding a second source of truth. Play
// money only: virtual ⓥ credits, paper trading at real venue prices.

import { API_URL } from "./api";
import { authHeaders, round2, type PortfolioOut, type TradeRecord, type TraderStorage } from "./trader";

/** One row in the trade-history table — the append-only execution shape. */
export type TradeRow = TradeRecord;

export interface TradeSummary {
  n: number; // total executions
  volume: number; // total notional traded (Σ shares × price), 2dp
  buys: number;
  sells: number;
}

/**
 * Fold a list of executions into headline counts. Pure and deterministic:
 * volume is true notional (shares × price), rounded once at the end to match
 * the backend's 2-decimal money boundary. Buys and sells are counted by
 * `action`, so they always sum to `n`.
 */
export function summarize(trades: TradeRow[]): TradeSummary {
  let volume = 0;
  let buys = 0;
  let sells = 0;
  for (const t of trades) {
    volume += t.shares * t.price;
    if (t.action === "buy") buys += 1;
    else if (t.action === "sell") sells += 1;
  }
  return { n: trades.length, volume: round2(volume), buys, sells };
}

/**
 * The caller's recent executions, newest first. Reuses GET
 * /api/markets/portfolio/me (which already returns `recent_trades`) so trading
 * identity flows through the standard X-API-Key header. Deps are injectable for
 * tests (no localStorage / global fetch needed).
 */
export async function getTradeHistory(
  deps: { storage?: TraderStorage; fetchImpl?: typeof fetch } = {},
): Promise<TradeRow[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/markets/portfolio/me`, {
    headers: authHeaders(deps.storage),
  });
  if (!res.ok) throw new Error(`trade history failed (${res.status})`);
  const body = (await res.json()) as PortfolioOut;
  return body.recent_trades ?? [];
}
