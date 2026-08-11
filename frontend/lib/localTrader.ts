// localStorage persistence for the in-browser play-money engine, so the
// static (GitHub Pages) demo is fully interactive with no backend. The trader's
// book lives only in this browser; clearing site data resets it to ⓥ10,000.

import {
  emptyTrader,
  executeLocalTrade,
  localPortfolio,
  type LocalMarket,
  type LocalTrade,
  type LocalTrader,
  STORAGE_KEY,
} from "./localTrading";

/** Minimal storage surface (localStorage in the browser, an in-memory stub in
 * tests) — same injection pattern as lib/starred.ts. */
export interface Storage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

function defaultStorage(): Storage | null {
  return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
}

/** Load the browser trader, or a fresh ⓥ10,000 book. Never throws. */
export function loadLocalTrader(storage: Storage | null = defaultStorage()): LocalTrader {
  if (!storage) return emptyTrader();
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return emptyTrader();
    const parsed = JSON.parse(raw) as LocalTrader;
    if (
      typeof parsed.balance !== "number" ||
      !Number.isFinite(parsed.balance) ||
      !Array.isArray(parsed.positions) ||
      !Array.isArray(parsed.trades)
    )
      return emptyTrader();
    return { balance: parsed.balance, positions: parsed.positions, trades: parsed.trades };
  } catch {
    return emptyTrader();
  }
}

function saveLocalTrader(t: LocalTrader, storage: Storage | null): void {
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(t));
  } catch {
    // storage full / disabled — the trade still applies for this session
  }
}

export function resetLocalTrader(storage: Storage | null = defaultStorage()): void {
  storage?.removeItem?.(STORAGE_KEY);
}

/** Execute a trade against the browser book and persist it. Throws
 * LocalTradeError (message is user-readable) on any rejection. */
export function placeLocalTrade(
  market: LocalMarket,
  side: "yes" | "no",
  action: "buy" | "sell",
  shares: number,
  storage: Storage | null = defaultStorage(),
): { trader: LocalTrader; trade: LocalTrade } {
  const result = executeLocalTrade(loadLocalTrader(storage), market, side, action, shares);
  saveLocalTrader(result.trader, storage);
  return result;
}

/** The browser book marked to the given current prices (and 1/0 settlement
 * values once a market's outcome is known). */
export function localPortfolioSnapshot(
  priceOf: (eventId: number) => number | null,
  outcomeOf: (eventId: number) => number | null = () => null,
  storage: Storage | null = defaultStorage(),
) {
  return localPortfolio(loadLocalTrader(storage), priceOf, outcomeOf);
}
