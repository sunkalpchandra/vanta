// Settled-markets resolution archive — the read-only settlement history of the
// play-money market: which real-venue events resolved, what they settled to,
// and whether the market's own final price called the outcome.
//
// Client-safe: no server-only imports (only the public API_URL). The client
// MarketArchive component imports getArchive + marketCalledIt from here for
// live paging; static demo mode reads the baked market-archive.json through
// lib/data.ts (a server-only module, integration) and hands the rows to the
// component as a prop instead — the same split as MarketsBrowser / marketStats.
//
// Play money · paper trading · real market prices — never real money.

import { API_URL } from "./api";

/** One settled real-venue market. `final_price` is the market's YES price at
 * settlement, so a reader can judge whether the market's own last price agreed
 * with the realized `outcome` (1 YES / 0 NO). */
export interface ArchiveItem {
  event_id: number;
  question: string;
  category: string;
  source: string; // polymarket | kalshi | manifold
  outcome: number | null; // 1 YES, 0 NO (the archive only lists resolved markets)
  final_price: number | null; // YES price at settlement, in (0,1)
  close_time: string | null;
  volume_usd: number;
}

/** GET /api/market-archive envelope: a cheap total plus one page of items. */
export interface ArchiveOut {
  total: number;
  items: ArchiveItem[];
}

/**
 * Did the market's own final price call the outcome? A final YES price above
 * 0.5 is the market leaning YES; that call is right when the market resolved
 * YES (outcome === 1). Returns:
 *   true  — the final price agreed with the realized outcome
 *   false — the final price disagreed
 *   null  — undecidable (no outcome, or no final price recorded)
 *
 * Pure and deterministic. A final price of exactly 0.5 counts as a NO lean
 * (strictly > 0.5 is required for YES), so it "calls it" only on a NO outcome.
 */
export function marketCalledIt(
  item: Pick<ArchiveItem, "outcome" | "final_price">,
): boolean | null {
  if (item.outcome === null || item.outcome === undefined) return null;
  if (item.final_price === null || item.final_price === undefined) return null;
  const marketLeansYes = item.final_price > 0.5;
  const resolvedYes = item.outcome === 1;
  return marketLeansYes === resolvedYes;
}

export interface GetArchiveOptions {
  category?: string; // omit or "all" for every category
  limit?: number;
  offset?: number;
  fetchImpl?: typeof fetch;
}

/**
 * Live fetch of a page of the settled-markets archive from the API. The API
 * returns a { total, items } envelope; a bare list is tolerated defensively
 * (same ethos as lib/data.ts / lib/marketStats.ts). Throws a readable Error on
 * a non-2xx response so a client caller can render an honest error state.
 *
 * Static demo mode never calls this — the archive page reads the baked
 * market-archive.json via lib/data.ts (getMarketArchiveSample, integration) and
 * passes the rows to MarketArchive as a prop.
 */
export async function getArchive(opts: GetArchiveOptions = {}): Promise<ArchiveOut> {
  const { category, limit = 50, offset = 0, fetchImpl } = opts;
  const doFetch = fetchImpl ?? fetch;
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (category && category !== "all") params.set("category", category);
  const res = await doFetch(`${API_URL}/api/market-archive?${params}`);
  if (!res.ok) throw new Error(`archive fetch failed (${res.status})`);
  const body = (await res.json()) as ArchiveOut | ArchiveItem[];
  if (Array.isArray(body)) return { total: body.length, items: body };
  return { total: body.total ?? body.items?.length ?? 0, items: body.items ?? [] };
}
