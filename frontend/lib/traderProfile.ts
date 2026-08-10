// Public trader-profile access + pure display helpers for the play-money
// prediction market. Client-safe: the only runtime import is API_URL, so both
// server and client components can import from here. Play money only — virtual
// ⓥ credits, paper trading at real synced venue prices, never real money.

import { API_URL } from "./api";
import type { TradeRecord } from "./trader";

/** One position in a trader's public book — mirrors the backend's
 * portfolio() row (no realized_pnl / api_key exposed). */
export interface ProfilePosition {
  event_id: number;
  question: string;
  side: "yes" | "no";
  shares: number;
  avg_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  settled: boolean;
}

/** The /api/traders/{name} response shape. The trader is addressed and shown by
 * their handle (email local-part) — the full email is never present. */
export interface TraderProfile {
  name: string;
  joined: string;
  balance: number;
  equity: number;
  realized_pnl: number;
  n_trades: number;
  positions: ProfilePosition[];
  recent_trades: TradeRecord[];
  note?: string;
}

/**
 * Fetch a public trader profile by handle. Returns null on 404 or any network
 * failure so callers can render notFound() / an empty state instead of
 * throwing. Live API only — static mode reads the baked leaderboard through
 * lib/data.ts (a server-only module) and renders a lightweight profile.
 */
export async function getTraderProfile(
  name: string,
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<TraderProfile | null> {
  const doFetch = deps.fetchImpl ?? fetch;
  try {
    const res = await doFetch(`${API_URL}/api/traders/${encodeURIComponent(name)}`);
    if (!res.ok) return null;
    return (await res.json()) as TraderProfile;
  } catch {
    return null; // backend offline — caller renders its empty state
  }
}

// --- pure display helpers (deterministic, unit-tested) ----------------------

/** Tailwind color class for a signed P&L figure: non-negative greens, else red.
 * Zero reads as flat-but-not-losing, so it greens (matches the leaderboard). */
export const pnlColor = (n: number): "text-pos" | "text-neg" =>
  n >= 0 ? "text-pos" : "text-neg";

/**
 * Share of a trader's marked-open positions currently in profit (unrealized
 * P&L > 0). Only open positions that still hold shares AND carry a numeric mark
 * count; settled, closed, and unmarked rows are ignored. Null when none
 * qualify (nothing to average).
 */
export function winRate(positions: ProfilePosition[]): number | null {
  const marked = positions.filter(
    (p) => !p.settled && p.shares > 0 && p.unrealized_pnl !== null,
  );
  if (marked.length === 0) return null;
  const winners = marked.filter((p) => (p.unrealized_pnl ?? 0) > 0).length;
  return winners / marked.length;
}
