// Client-side play-money trading engine — the browser equivalent of the
// Python app/trading.py, so the GitHub Pages static demo is fully interactive
// with no backend. State lives in localStorage; nothing is ever sent anywhere.
//
// The money math mirrors the backend EXACTLY (verified by parity tests):
// house-favorable cent rounding (charges up, payouts down) so no dust-trade
// can mint credits, a minimum notional on both sides, prices strictly in
// (0,1), sells capped at held shares, weighted-average cost basis. Play money
// only — ⓥ credits are virtual and worthless.

export const STARTING_BALANCE = 10_000;
export const MIN_NOTIONAL = 0.01;
export const STORAGE_KEY = "vanta:local-trader";

export interface LocalMarket {
  id: number;
  question: string;
  yes_price: number | null;
  outcome: number | null;
  close_time?: string | null;
}

export interface LocalPosition {
  event_id: number;
  question: string;
  side: "yes" | "no";
  shares: number;
  avg_price: number;
  realized_pnl: number;
  settled: boolean;
}

export interface LocalTrade {
  id: number;
  event_id: number;
  question: string;
  side: "yes" | "no";
  action: "buy" | "sell";
  shares: number;
  price: number;
  cost: number; // signed balance delta (negative = spent)
  created_at: string;
}

export interface LocalTrader {
  balance: number;
  positions: LocalPosition[];
  trades: LocalTrade[];
}

export class LocalTradeError extends Error {}

/** Round a charge-to-the-trader UP to the cent (mirrors backend _debit). */
export function debit(amount: number): number {
  return Math.ceil(amount * 100 - 1e-9) / 100;
}

/** Round a payout-to-the-trader DOWN to the cent (mirrors backend _credit). */
export function credit(amount: number): number {
  return Math.floor(amount * 100 + 1e-9) / 100;
}

/** Round half-to-even at 2 decimals — matches Python's round() (banker's),
 * which the backend _round_money uses. Plain Math.round is half-UP and would
 * diverge by a cent on exact half-cent values (e.g. 0.125 -> 0.12, not 0.13). */
function round2(amount: number): number {
  const scaled = amount * 100;
  const floor = Math.floor(scaled);
  const diff = scaled - floor;
  let cents: number;
  if (Math.abs(diff - 0.5) < 1e-9) {
    cents = floor % 2 === 0 ? floor : floor + 1; // tie -> even
  } else {
    cents = Math.round(scaled);
  }
  return cents / 100 + 0;
}

/** Execution price per share: YES at the venue price, NO at its complement. */
export function execPrice(yesPrice: number, side: "yes" | "no"): number {
  const p = side === "yes" ? yesPrice : 1 - yesPrice;
  return Math.round(p * 1e6) / 1e6;
}

export function emptyTrader(): LocalTrader {
  return { balance: STARTING_BALANCE, positions: [], trades: [] };
}

function findPosition(t: LocalTrader, eventId: number, side: "yes" | "no"): LocalPosition | undefined {
  return t.positions.find((p) => p.event_id === eventId && p.side === side);
}

function nextTradeId(t: LocalTrader): number {
  return t.trades.reduce((m, x) => Math.max(m, x.id), 0) + 1;
}

/** A stable clock hook so tests can inject time; defaults to now. */
export interface EngineDeps {
  now?: () => Date;
}

/** Execute one play-money trade against a LocalTrader, returning the updated
 * trader plus the appended trade. Throws LocalTradeError on any business-rule
 * rejection — the same rejections the backend raises. Pure: it returns a new
 * trader rather than mutating the input. */
export function executeLocalTrade(
  trader: LocalTrader,
  market: LocalMarket,
  side: "yes" | "no",
  action: "buy" | "sell",
  shares: number,
  deps: EngineDeps = {},
): { trader: LocalTrader; trade: LocalTrade } {
  if (side !== "yes" && side !== "no") throw new LocalTradeError("side must be 'yes' or 'no'");
  if (action !== "buy" && action !== "sell") throw new LocalTradeError("action must be 'buy' or 'sell'");
  if (!(shares > 0)) throw new LocalTradeError("shares must be greater than 0");
  if (market.outcome !== null && market.outcome !== undefined)
    throw new LocalTradeError("event already resolved");
  if (market.yes_price === null || market.yes_price === undefined)
    throw new LocalTradeError("event has no synced price yet");
  if (!(market.yes_price > 0 && market.yes_price < 1))
    throw new LocalTradeError("venue price is outside (0, 1) — not tradeable");
  if (market.close_time) {
    const close = new Date(market.close_time.endsWith("Z") ? market.close_time : market.close_time + "Z");
    const now = deps.now ? deps.now() : new Date();
    if (close.getTime() <= now.getTime())
      throw new LocalTradeError("event has passed its close time — trading is halted");
  }

  const price = execPrice(market.yes_price, side);
  // Deep-ish copy so we never mutate the caller's state.
  const t: LocalTrader = {
    balance: trader.balance,
    positions: trader.positions.map((p) => ({ ...p })),
    trades: trader.trades.slice(),
  };
  let position = findPosition(t, market.id, side);
  if (position && position.settled) throw new LocalTradeError("position already settled");

  let executed: number;
  let delta: number;
  if (action === "buy") {
    if (shares * price < MIN_NOTIONAL)
      throw new LocalTradeError(`trade too small — notional must be at least ⓥ${MIN_NOTIONAL.toFixed(2)}`);
    const cost = debit(shares * price);
    if (cost > t.balance + 1e-9)
      throw new LocalTradeError(`insufficient balance: cost ⓥ${cost.toFixed(2)} exceeds ⓥ${t.balance.toFixed(2)}`);
    if (!position) {
      position = { event_id: market.id, question: market.question, side, shares: 0, avg_price: 0, realized_pnl: 0, settled: false };
      t.positions.push(position);
    }
    const totalShares = position.shares + shares;
    position.avg_price = (position.shares * position.avg_price + shares * price) / totalShares;
    position.shares = totalShares;
    t.balance = round2(t.balance - cost);
    executed = shares;
    delta = -cost;
  } else {
    if (!position || position.shares <= 0) throw new LocalTradeError("no shares to sell");
    executed = Math.min(shares, position.shares);
    if (executed * price < MIN_NOTIONAL && executed < position.shares - 1e-9)
      throw new LocalTradeError(`sell too small — notional must be at least ⓥ${MIN_NOTIONAL.toFixed(2)}`);
    const proceeds = credit(executed * price);
    const realized = round2(executed * (price - position.avg_price));
    position.shares = Math.round((position.shares - executed) * 1e9) / 1e9;
    if (position.shares < 1e-9) position.shares = 0;
    position.realized_pnl = round2(position.realized_pnl + realized);
    t.balance = round2(t.balance + proceeds);
    delta = proceeds;
  }

  const trade: LocalTrade = {
    id: nextTradeId(t),
    event_id: market.id,
    question: market.question,
    side,
    action,
    shares: executed,
    price,
    cost: delta,
    created_at: (deps.now ? deps.now() : new Date()).toISOString(),
  };
  t.trades.push(trade);
  return { trader: t, trade };
}

/** Mark-to-market account view against the given current prices (by event id). */
export function localPortfolio(
  trader: LocalTrader,
  priceOf: (eventId: number) => number | null,
  outcomeOf: (eventId: number) => number | null = () => null,
): {
  balance: number;
  equity: number;
  realized_pnl_total: number;
  unrealized_pnl_total: number;
  positions: (LocalPosition & { current_price: number | null; unrealized_pnl: number })[];
} {
  let marketValue = 0;
  let realizedTotal = 0;
  let unrealizedTotal = 0;
  const positions = trader.positions.map((p) => {
    realizedTotal += p.realized_pnl;
    // Once a market has resolved, a position is worth its settlement value
    // (ⓥ1 if this side won, ⓥ0 if it lost) — not the last stale venue price.
    // Mirrors the backend _mark_price.
    const outcome = outcomeOf(p.event_id);
    let current: number | null;
    if (outcome === 0 || outcome === 1) {
      current = (p.side === "yes") === (outcome === 1) ? 1 : 0;
    } else {
      const yes = priceOf(p.event_id);
      current = yes === null ? null : execPrice(yes, p.side);
    }
    let unrealized = 0;
    if (current !== null && p.shares > 0) {
      marketValue += p.shares * current;
      unrealized = round2(p.shares * (current - p.avg_price));
    }
    unrealizedTotal += unrealized;
    return { ...p, current_price: current, unrealized_pnl: unrealized };
  });
  return {
    balance: round2(trader.balance),
    equity: round2(trader.balance + marketValue),
    realized_pnl_total: round2(realizedTotal),
    unrealized_pnl_total: round2(unrealizedTotal),
    positions,
  };
}
