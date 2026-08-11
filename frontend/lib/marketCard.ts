// Shareable market-card helpers: where a market's SVG card lives in the current
// mode, plus a pure builder for og:image alt text.
//
// Client-safe: only lib/api's public API_URL + lib/config (no filesystem), so
// client components may import it. Mirrors lib/api.ts's shareCardHref (question
// cards) for the play-money markets surface.
//
// Play money only — virtual ⓥ credits, paper trading at real synced venue
// prices, never real money.

import { API_URL } from "./api";
import { BASE_PATH, IS_STATIC } from "./config";
import { pct } from "./format";
import { formatCompactUsd } from "./marketStats";
import type { MarketItem } from "./types";

/** Where the share-card SVG for a market event lives in the current mode.
 * Static mode reads the baked file under the Pages basePath; live mode hits the
 * backend router (distinct /api/market-cards prefix — no /api/markets clash). */
export const marketCardHref = (eventId: number) =>
  IS_STATIC
    ? `${BASE_PATH}/market-cards/${eventId}.svg`
    : `${API_URL}/api/market-cards/${eventId}.svg`;

/** The fields buildOgDescription reads — a structural subset of MarketItem. */
export type OgMarket = Pick<
  MarketItem,
  "question" | "source" | "yes_price" | "volume_usd" | "outcome"
>;

/**
 * Alt text for the market card's og:image — one honest line describing the
 * market. Pure and total: a settled market reads "resolved YES/NO"; an open one
 * reads the YES price and compact volume; a missing price degrades to "price
 * pending" rather than "NaN%". Always carries the play-money label so a shared
 * card can never imply real stakes. Outcome uses 1=YES / 0=NO (0 is real — test
 * for null/undefined explicitly, never truthiness).
 */
export function buildOgDescription(market: OgMarket): string {
  const question = market.question?.trim() || "Untitled market";
  const source = market.source?.trim() || "market";

  if (market.outcome !== null && market.outcome !== undefined) {
    const settled = market.outcome === 1 ? "YES" : "NO";
    return `${question} — resolved ${settled} on ${source} (play money)`;
  }

  const price =
    typeof market.yes_price === "number" && Number.isFinite(market.yes_price)
      ? `${pct(market.yes_price)} YES`
      : "price pending";
  const volume = formatCompactUsd(market.volume_usd ?? 0);
  return `${question} — ${price} on ${source}, ${volume} volume (play money)`;
}
