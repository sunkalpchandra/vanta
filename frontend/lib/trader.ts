// Client-side trader identity + shared types for the play-money prediction
// market. The API key ("vk_...") returned once by POST /api/users IS the
// trading identity — held in localStorage, sent as X-API-Key on every trading
// call. Play money only: virtual ⓥ credits, paper trading at real venue
// prices, never real money.

import { API_URL } from "./api";

const KEY = "vanta:trader-key";

export type TraderStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function getTraderKey(storage: TraderStorage = localStorage): string | null {
  const raw = storage.getItem(KEY);
  return raw && raw.trim() !== "" ? raw : null;
}

export function setTraderKey(key: string, storage: TraderStorage = localStorage): void {
  storage.setItem(KEY, key);
}

export function clearTraderKey(storage: TraderStorage = localStorage): void {
  storage.removeItem(KEY);
}

/** Headers for authenticated trading calls; empty when no identity yet. */
export function authHeaders(storage: TraderStorage = localStorage): Record<string, string> {
  const key = getTraderKey(storage);
  return key ? { "X-API-Key": key } : {};
}

export interface EnsureTraderResult {
  key: string;
  created: boolean;
}

/** FastAPI errors carry {detail} — surface it when present, else fall back. */
export async function readableError(
  res: Pick<Response, "json">,
  fallback: string,
): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body?.detail === "string" && body.detail) return body.detail;
  } catch {
    // non-JSON body — keep the fallback
  }
  return fallback;
}

/**
 * Return the stored trader key, registering a new play-money trader
 * (POST /api/users) when none exists. The backend shows the key exactly once,
 * so it is stored immediately. Throws a readable Error on failure — including
 * the 409 "email already registered" (the original key cannot be re-fetched).
 */
export async function ensureTrader(
  email?: string,
  deps: { storage?: TraderStorage; fetchImpl?: typeof fetch } = {},
): Promise<EnsureTraderResult> {
  const storage = deps.storage ?? localStorage;
  const existing = getTraderKey(storage);
  if (existing) return { key: existing, created: false };
  const trimmed = email?.trim() ?? "";
  if (!trimmed) throw new Error("email required to start trading");
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: trimmed }),
  });
  if (!res.ok) throw new Error(await readableError(res, `registration failed (${res.status})`));
  const body = (await res.json()) as { api_key?: string };
  if (!body.api_key) throw new Error("registration response missing api_key");
  setTraderKey(body.api_key, storage);
  return { key: body.api_key, created: true };
}

// ---------------------------------------------------------------------------
// Pure money/display helpers — deterministic, boundary-rounded to 2 decimals.

export const round2 = (n: number) => Math.round(n * 100) / 100;

/** Execution price for a side given the venue YES price; null when untradable. */
export function sidePrice(yesPrice: number | null, side: "yes" | "no"): number | null {
  if (yesPrice === null || !(yesPrice > 0 && yesPrice < 1)) return null;
  return side === "yes" ? yesPrice : 1 - yesPrice;
}

/**
 * Cost/proceeds preview, rounded to the cent to match the backend: buys round
 * the cost UP (you never pay less than the true notional), sells round the
 * proceeds DOWN. Null when inputs are invalid.
 */
export function tradeCost(
  shares: number,
  price: number | null,
  direction: "buy" | "sell",
): number | null {
  if (price === null || !(shares > 0) || !(price > 0 && price < 1)) return null;
  const cents = shares * price * 100;
  return (direction === "buy" ? Math.ceil(cents) : Math.floor(cents)) / 100;
}

/** ⓥ credit amount, always 2dp. */
export const fmtCredits = (n: number) =>
  `ⓥ${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Signed ⓥ amount for P&L readouts: "+ⓥ12.50" / "-ⓥ12.50". */
export const fmtSignedCredits = (n: number) => `${n < 0 ? "-" : "+"}${fmtCredits(n)}`;

/** Compact venue volume: "$1.2m", "$530k", "$980". */
export function compactUsd(n: number): string {
  const fmt = (x: number) => (x >= 100 ? String(Math.round(x)) : x.toFixed(1).replace(/\.0$/, ""));
  if (n >= 1e9) return `$${fmt(n / 1e9)}b`;
  if (n >= 1e6) return `$${fmt(n / 1e6)}m`;
  if (n >= 1e3) return `$${fmt(n / 1e3)}k`;
  return `$${Math.round(n)}`;
}

// JS parses offset-less ISO stamps as LOCAL time; the API's UTC stamps need
// the Z appended (same defense as lib/format.ts).
const asUtc = (iso: string) => (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);

/** Whole days until close (ceil); null when unknown, unparsable, or past. */
export function daysUntilClose(iso: string | null, now: Date = new Date()): number | null {
  if (!iso) return null;
  const t = Date.parse(asUtc(iso));
  if (Number.isNaN(t)) return null;
  const days = Math.ceil((t - now.getTime()) / 86_400_000);
  return days >= 0 ? days : null;
}

// ---------------------------------------------------------------------------
// API shapes (backend contract — integration reconciles).

export interface MarketItem {
  id: number;
  question: string;
  category: string;
  source: string; // polymarket | kalshi
  yes_price: number | null; // probability of YES in (0,1); null until synced
  volume_usd: number;
  close_time: string | null;
  outcome: number | null; // 1 YES, 0 NO, null unresolved
}

export interface MarketsOut {
  total: number;
  items: MarketItem[];
}

export interface PositionOut {
  event_id: number;
  side: "yes" | "no";
  shares: number;
  avg_price: number;
  realized_pnl: number;
  settled: boolean;
}

export interface TradeRecord {
  id: number;
  event_id: number;
  question?: string;
  side: "yes" | "no";
  action: "buy" | "sell";
  shares: number;
  price: number;
  cost: number; // signed balance delta (negative = spent)
  created_at: string;
}

export interface TradeResponse {
  balance: number;
  position: PositionOut;
  trade: TradeRecord;
}

export interface PortfolioPosition extends PositionOut {
  question: string;
  current_price: number | null;
  unrealized_pnl: number | null;
}

export interface PortfolioOut {
  balance: number;
  equity: number;
  realized_pnl_total: number;
  positions: PortfolioPosition[];
  recent_trades?: TradeRecord[];
}
