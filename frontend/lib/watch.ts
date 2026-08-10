// Per-trader market watchlist — server-truth (unlike the localStorage reader
// star in lib/starred). The list lives on the backend keyed to the trader's
// X-API-Key, so it follows the account across browsers. Play money only:
// virtual ⓥ credits, paper trading at real venue prices, never real money.

import { API_URL } from "./api";
import { authHeaders, type TraderStorage } from "./trader";

// A watched market has "moved" when its trailing-24h price shifted at least
// this far (5 probability points) — mirrors the backend MOVE_THRESHOLD so the
// client never disagrees with the server about what counts as a move.
export const MOVE_THRESHOLD = 0.05;

export interface WatchItem {
  event_id: number;
  question: string;
  yes_price: number | null;
  delta_24h: number | null; // current price − earliest in-window tick; null if unknowable
  moved: boolean;
}

/**
 * Whether a 24h delta counts as a move. Pure and total: a null/undefined or
 * non-finite delta is not a move. Kept in lockstep with the backend threshold.
 */
export function isMoved(delta: number | null | undefined): boolean {
  return delta != null && Number.isFinite(delta) && Math.abs(delta) >= MOVE_THRESHOLD;
}

interface WatchDeps {
  fetchImpl?: typeof fetch;
  storage?: TraderStorage;
}

/**
 * The caller's watched markets from GET /api/watch, sent with the trader key.
 * Returns [] when there is no identity yet or the request fails — a watchlist
 * is a soft signal, never a reason to break the surface it decorates.
 */
export async function getWatched(deps: WatchDeps = {}): Promise<WatchItem[]> {
  const headers = authHeaders(deps.storage);
  if (!("X-API-Key" in headers)) return []; // no trader identity → nothing watched
  const doFetch = deps.fetchImpl ?? fetch;
  try {
    const res = await doFetch(`${API_URL}/api/watch`, { headers });
    if (!res.ok) return [];
    return (await res.json()) as WatchItem[];
  } catch {
    return []; // backend down — degrade to an empty watchlist
  }
}

/** The watched event ids only — for cheaply marking rows as watched. */
export async function getWatchedIds(deps: WatchDeps = {}): Promise<number[]> {
  return (await getWatched(deps)).map((w) => w.event_id);
}

/**
 * Add (on=true → POST) or remove (on=false → DELETE) a watch. POST is
 * idempotent (200/201); DELETE returns 204, or 404 when it was already gone —
 * both of which mean "now unwatched", so both resolve to true. Throws when
 * there is no trader identity to act as. Returns whether the server agrees the
 * watch is now in the requested state.
 */
export async function toggleWatch(id: number, on: boolean, deps: WatchDeps = {}): Promise<boolean> {
  const headers = authHeaders(deps.storage);
  if (!("X-API-Key" in headers)) throw new Error("start trading to build a watchlist");
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/watch/${id}`, { method: on ? "POST" : "DELETE", headers });
  return on ? res.ok : res.ok || res.status === 404;
}
