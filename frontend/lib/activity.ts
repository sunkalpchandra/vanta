// Public activity-tape helpers for the play-money prediction market.
//
// Client-safe: no server-only imports (only API_URL + the pure percent
// formatter), so the ActivityTape client component can import from here
// directly. Play money only — virtual ⓥ credits, paper trading at real venue
// prices, never real money.

import { API_URL } from "./api";
import { pct } from "./format";

/** One recent trade on the public tape (all traders, newest first). Mirrors the
 * backend /api/activity/trades row; the static snapshot bakes the same shape. */
export interface TradeTapeItem {
  id: number;
  trader: string; // email local-part or agent name — never a full email
  event_id: number;
  question: string;
  side: "yes" | "no";
  action: "buy" | "sell";
  shares: number;
  price: number; // execution price per share in (0, 1)
  created_at: string;
}

/** The /api/activity/trades envelope (and the baked activity.json shape). */
export interface ActivityFeed {
  trades: TradeTapeItem[];
  note: string;
}

const DEFAULT_LIMIT = 30;

/**
 * Live recent-trades fetch — all traders, newest first. Covers the live API
 * only; static mode reads a baked snapshot through lib/data.ts (a server-only
 * module) and hands the result to the component as a prop instead.
 */
export async function getActivity(
  limit: number = DEFAULT_LIMIT,
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<TradeTapeItem[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/activity/trades?limit=${limit}`);
  if (!res.ok) throw new Error(`activity fetch failed (${res.status})`);
  const body = (await res.json()) as Partial<ActivityFeed>;
  return body.trades ?? [];
}

/** Whole shares print bare; fractional lots keep at most 2 decimals. */
function formatShares(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
}

/** Truncate to `max` visible chars, appending an ellipsis when clipped. */
function truncate(text: string, max: number): string {
  const t = text.trim();
  return t.length <= max ? t : `${t.slice(0, max - 1).trimEnd()}…`;
}

/**
 * One-line tape summary, e.g. "alice bought 100 YES @ 42% · Will BTC …".
 * Pure and deterministic — unit-tested and rendered verbatim by the component.
 */
export function formatTapeLine(item: TradeTapeItem, maxQuestion = 48): string {
  const verb = item.action === "buy" ? "bought" : "sold";
  const head = `${item.trader} ${verb} ${formatShares(item.shares)} ${item.side.toUpperCase()} @ ${pct(item.price)}`;
  return `${head} · ${truncate(item.question, maxQuestion)}`;
}
