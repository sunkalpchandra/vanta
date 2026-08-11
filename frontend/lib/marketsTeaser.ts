// Homepage markets-teaser helpers for the play-money market. Pure ranking
// (pickTopMovers) plus one combined getter that reuses the existing
// market-surface fetches in lib/marketStats — so the teaser never opens a
// second contract with the backend.
//
// Client-safe: no server-only imports (only lib/marketStats, itself client
// safe). Static mode bakes stats/movers via lib/data.ts and hands them to the
// MarketsTeaser component as props instead of calling getMarketsTeaser.
//
// Play money only — virtual ⓥ credits, paper trading at real synced venue
// prices, never real money.

import { getMarketStats, getMovers, type MarketMover, type MarketStats } from "./marketStats";

/**
 * The `n` biggest movers by absolute price change, largest first. Pure and
 * total: a non-array input or `n <= 0` yields []; a non-finite `change` sorts
 * as no move (sinks to the bottom) rather than poisoning the order. Ties break
 * deterministically — larger venue volume first, then lower event_id — so the
 * same input always renders the same teaser. Does not mutate the input.
 */
export function pickTopMovers(movers: MarketMover[], n: number): MarketMover[] {
  if (!Array.isArray(movers) || n <= 0) return [];
  const mag = (change: number) => (Number.isFinite(change) ? Math.abs(change) : 0);
  return [...movers]
    .sort(
      (a, b) =>
        mag(b.change) - mag(a.change) ||
        b.volume_usd - a.volume_usd ||
        a.event_id - b.event_id,
    )
    .slice(0, n);
}

export interface MarketsTeaserData {
  stats: MarketStats | null;
  movers: MarketMover[];
}

/**
 * The homepage teaser payload: market-surface stats plus the top-`n` movers of
 * the last 24h, reusing lib/marketStats' getters (same window/limit the static
 * export bakes). Stats are decorative — a stats hiccup degrades to null — but a
 * movers failure propagates, so the component can show an honest "backend
 * down" state instead of a silently empty card.
 */
export async function getMarketsTeaser(
  n = 3,
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<MarketsTeaserData> {
  const [stats, movers] = await Promise.all([
    getMarketStats(deps).catch(() => null),
    getMovers(24, 20, deps),
  ]);
  return { stats, movers: pickTopMovers(movers, n) };
}
