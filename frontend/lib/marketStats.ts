// Market-surface stats + biggest-movers helpers for the play-money market.
//
// Client-safe: no server-only imports (only the public API_URL). Both the
// MarketStatsBar and MarketMovers client components import from here for live
// fetches; static mode reads baked snapshots through lib/data.ts (a server-only
// module) and hands the result to the components as props instead.
//
// Play money only — virtual ⓥ credits, paper trading at real synced venue
// prices, never real money.

import { API_URL } from "./api";

/** Active-surface breakdown by venue (mirrors the backend BySource). */
export interface MarketSourceBreakdown {
  polymarket: number;
  kalshi: number;
  manifold: number;
}

/** GET /api/market-stats — corpus-wide surface counts for the stat bar. */
export interface MarketStats {
  n_active: number;
  n_settled: number;
  by_source: MarketSourceBreakdown;
  total_volume_usd: number;
  n_traders: number;
  n_open_positions: number;
  n_trades: number;
}

/** One row of GET /api/market-stats/movers. `change` is signed (current - prev,
 * in probability units); positive = the YES price moved up over the window. */
export interface MarketMover {
  event_id: number;
  question: string;
  source: string;
  yes_price: number;
  prev_price: number;
  change: number;
  volume_usd: number;
}

/** Up / down / flat direction of a mover, from its rounded whole-percent move.
 * Rounded (not raw sign) so the tone can't disagree with the displayed label —
 * a change that renders as "0%" reads as flat. */
export function moverTone(change: number): "pos" | "neg" | "flat" {
  const pts = Math.round(change * 100);
  return pts > 0 ? "pos" : pts < 0 ? "neg" : "flat";
}

/**
 * Compact delta label for a mover, e.g. "▲ +30%", "▼ -12%", "→ 0%". Pure and
 * deterministic — unit-tested and rendered verbatim by MarketMovers. The arrow
 * and sign are derived from the SAME rounded value as the number, so they never
 * contradict it.
 */
export function formatMoverDelta(change: number): string {
  const pts = Math.round(change * 100);
  const arrow = pts > 0 ? "▲" : pts < 0 ? "▼" : "→";
  const sign = pts > 0 ? "+" : ""; // a negative sign already prints on the number
  return `${arrow} ${sign}${pts}%`;
}

/**
 * Compact USD, e.g. 1234 -> "$1.2K", 3_400_000 -> "$3.4M", 950 -> "$950". One
 * decimal for K/M/B (trailing ".0" trimmed by Number), whole dollars below 1K.
 * Pure — unit-tested; used for the volume stat tile.
 */
export function formatCompactUsd(n: number): string {
  const abs = Math.abs(n);
  const scaled = (value: number, suffix: string) => `$${Math.round(value * 10) / 10}${suffix}`;
  if (abs >= 1e9) return scaled(n / 1e9, "B");
  if (abs >= 1e6) return scaled(n / 1e6, "M");
  if (abs >= 1e3) return scaled(n / 1e3, "K");
  return `$${Math.round(n)}`;
}

/** Live fetch of the market-surface stats. Throws a readable Error on a non-2xx
 * response so a client caller can show an honest error state. */
export async function getMarketStats(deps: { fetchImpl?: typeof fetch } = {}): Promise<MarketStats> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/market-stats`);
  if (!res.ok) throw new Error(`market stats fetch failed (${res.status})`);
  return (await res.json()) as MarketStats;
}

/**
 * Live fetch of the biggest movers over `windowHours`. The API returns a bare
 * list; an object envelope ({ movers: [...] }) is tolerated defensively (same
 * ethos as lib/data.ts / lib/marketDetail.ts). Throws on a non-2xx response.
 */
export async function getMovers(
  windowHours = 24,
  limit = 20,
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<MarketMover[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(
    `${API_URL}/api/market-stats/movers?window_hours=${windowHours}&limit=${limit}`,
  );
  if (!res.ok) throw new Error(`movers fetch failed (${res.status})`);
  const body = (await res.json()) as MarketMover[] | { movers?: MarketMover[] };
  return Array.isArray(body) ? body : (body.movers ?? []);
}
