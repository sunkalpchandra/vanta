// Global market-search helpers for the play-money market.
//
// Client-safe: no server-only imports (only the public API_URL and type-only
// imports from ./types). The MarketSearch client component imports the live
// fetcher (searchMarkets) and the pure highlight/sample helpers from here;
// static mode filters the baked markets-sample entirely client-side via
// searchSample, so the demo never needs a backend.
//
// Play money only — virtual ⓥ credits, paper trading at real synced venue
// prices, never real money.

import { API_URL } from "./api";
import type { MarketItem } from "./types";

export type SearchStatus = "active" | "settled" | "all";

/** One search result — mirrors the backend GET /api/market-search item shape. */
export interface SearchHit {
  event_id: number;
  question: string;
  category: string;
  source: string; // polymarket | kalshi | manifold
  yes_price: number | null; // probability of YES in (0,1); null until synced
  outcome: number | null; // 1 YES, 0 NO, null unresolved
  active: boolean; // tradeable right now
}

interface SearchEnvelope {
  query: string;
  items: SearchHit[];
}

/** The shortest query the backend accepts (Query min_length=2). Static-mode
 * search enforces the same floor so both modes behave identically. */
export const MIN_QUERY_LEN = 2;

/**
 * Live search over the real-event corpus. Hits GET /api/market-search and
 * returns the items; an object envelope ({ items: [...] }) is unwrapped, a bare
 * list tolerated defensively (same ethos as lib/marketStats). Throws a readable
 * Error on a non-2xx response so a client caller can show an honest error state.
 */
export async function searchMarkets(
  q: string,
  status: SearchStatus = "active",
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<SearchHit[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  const params = new URLSearchParams({ q, status });
  const res = await doFetch(`${API_URL}/api/market-search?${params}`);
  if (!res.ok) throw new Error(`market search failed (${res.status})`);
  const body = (await res.json()) as SearchEnvelope | SearchHit[];
  return Array.isArray(body) ? body : (body.items ?? []);
}

function toHit(m: MarketItem): SearchHit {
  return {
    event_id: m.id,
    question: m.question,
    category: m.category,
    source: m.source,
    yes_price: m.yes_price,
    outcome: m.outcome,
    active: m.outcome === null, // sample rows: unresolved == still active
  };
}

/**
 * Static-mode search: filter the baked markets-sample client-side, mirroring
 * the API's semantics (case-insensitive substring, `status` scope, active-first
 * then by descending volume then id) so the demo ranks results identically to
 * the live backend. Pure and total — a query shorter than MIN_QUERY_LEN, a
 * non-array `items`, or `limit <= 0` yields []. Does not mutate its input.
 */
export function searchSample(
  items: MarketItem[],
  q: string,
  status: SearchStatus = "active",
  limit = 50,
): SearchHit[] {
  const needle = (q ?? "").trim().toLowerCase();
  if (!Array.isArray(items) || needle.length < MIN_QUERY_LEN || limit <= 0) return [];
  const rank = (m: MarketItem) => (m.outcome === null ? 0 : 1); // active first
  return items
    .filter((m) => {
      const active = m.outcome === null;
      if (status === "active" && !active) return false;
      if (status === "settled" && active) return false;
      return m.question.toLowerCase().includes(needle);
    })
    .sort((a, b) => rank(a) - rank(b) || b.volume_usd - a.volume_usd || a.id - b.id)
    .slice(0, limit)
    .map(toHit);
}

/** One run of the question, flagged whether it is part of the matched query. */
export interface HighlightPart {
  text: string;
  match: boolean;
}

/**
 * Split `question` into runs so a renderer can bold the matched substring(s).
 * Case-insensitive and every occurrence is flagged; the ORIGINAL casing is
 * preserved in the returned text. Pure and total: a blank/whitespace-only query
 * (or one that never occurs) yields a single unmatched run of the whole
 * question; an empty question yields []. Plain string scan (indexOf), never a
 * regex, so query metacharacters can't break it.
 */
export function highlightMatch(question: string, q: string): HighlightPart[] {
  const source = question ?? "";
  const needle = (q ?? "").trim();
  if (!needle) return source ? [{ text: source, match: false }] : [];
  const hay = source.toLowerCase();
  const find = needle.toLowerCase();
  const parts: HighlightPart[] = [];
  let i = 0;
  while (i <= source.length) {
    const at = hay.indexOf(find, i);
    if (at === -1) {
      if (i < source.length) parts.push({ text: source.slice(i), match: false });
      break;
    }
    if (at > i) parts.push({ text: source.slice(i, at), match: false });
    parts.push({ text: source.slice(at, at + find.length), match: true });
    i = at + find.length;
  }
  if (parts.length) return parts;
  return source ? [{ text: source, match: false }] : [];
}
