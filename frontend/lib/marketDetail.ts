// Market-detail helpers for the play-money markets surface: a pure builder for
// the YES-price chart series plus a client-side fetcher for a market's synced
// price history. Client-safe (only lib/api's public API_URL, no filesystem) —
// so client components may import it, unlike lib/data.ts.
//
// Play money only: the prices are real synced venue prices; trading against
// them is paper trading in virtual ⓥ credits.

import { API_URL } from "./api";

// Raw history-point shapes tolerated from the backend. The dedicated markets
// price-history endpoint is being built in parallel (see integration_needs),
// so its exact field names aren't pinned: accept the PriceTick-native
// {timestamp, yes_price}, the {timestamp, probability} shape the questions
// market-history endpoint uses, and a unix {t, p}/{t, price} ingest fallback.
export interface RawPricePoint {
  timestamp?: string | null;
  t?: string | number | null;
  yes_price?: number | null;
  probability?: number | null;
  price?: number | null;
  p?: number | null;
}

// One chart row: `t` is the ISO timestamp, `price` is the YES price as 0-100.
export interface PriceRow {
  t: string;
  price: number;
}

const clamp100 = (n: number) => (n < 0 ? 0 : n > 100 ? 100 : n);

// JS parses offset-less ISO stamps as LOCAL time; the API's UTC stamps need a
// trailing Z (same defense as lib/format.ts and lib/trader.ts).
const asUtc = (iso: string) => (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);

/** YES price in (0..1) from whichever field the point carries. 0.0 is a real
 * observation, so test for null/undefined explicitly — never truthiness. */
function pickPrice(point: RawPricePoint): number | null {
  const raw = point.yes_price ?? point.probability ?? point.price ?? point.p;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

/** ISO timestamp from `timestamp`/`t`; a numeric `t` is unix seconds. */
function pickTime(point: RawPricePoint): string | null {
  if (typeof point.timestamp === "string" && point.timestamp) return point.timestamp;
  if (typeof point.t === "string" && point.t) return point.t;
  if (typeof point.t === "number" && Number.isFinite(point.t)) {
    return new Date(point.t * 1000).toISOString();
  }
  return null;
}

/**
 * Build the YES-price chart series: {t, price} rows with price as a 0-100
 * percentage (one decimal, clamped to [0,100]), sorted oldest→newest and
 * deduped by exact timestamp (last write wins). Points missing a usable
 * timestamp or price are dropped.
 */
export function buildPriceSeries(points: RawPricePoint[] | null | undefined): PriceRow[] {
  const byTs = new Map<string, PriceRow>();
  for (const point of points ?? []) {
    const t = pickTime(point);
    const raw = pickPrice(point);
    if (t === null || raw === null) continue;
    byTs.set(t, { t, price: clamp100(+(raw * 100).toFixed(1)) });
  }
  return Array.from(byTs.values()).sort((a, b) => a.t.localeCompare(b.t));
}

// The endpoint may return a bare array (FastAPI list[...] response_model, as
// the questions market-history does) or a wrapped object; tolerate both.
type HistoryBody =
  | RawPricePoint[]
  | { history?: RawPricePoint[]; points?: RawPricePoint[]; ticks?: RawPricePoint[] };

function extractPoints(body: HistoryBody): RawPricePoint[] {
  if (Array.isArray(body)) return body;
  return body.history ?? body.points ?? body.ticks ?? [];
}

/**
 * Client-side fetch of a market's synced YES-price history, returned as the
 * built {t, price} series. Throws a readable Error on a non-2xx response so the
 * caller can show an honest error state.
 *
 * ASSUMPTION: the endpoint is GET /api/markets/{id}/history. The dedicated
 * backend router does not exist yet — until it ships this 404s and the detail
 * page surfaces its "couldn't load" state (tracked in integration_needs).
 */
export async function getMarketHistory(
  id: number | string,
  fetchImpl: typeof fetch = fetch,
): Promise<PriceRow[]> {
  const res = await fetchImpl(`${API_URL}/api/markets/${id}/history`);
  if (!res.ok) throw new Error(`history fetch failed (${res.status})`);
  return buildPriceSeries(extractPoints((await res.json()) as HistoryBody));
}

/** Localized date+time for a chart tooltip; offset-less stamps read as UTC. */
export function formatStamp(iso: string): string {
  const d = new Date(asUtc(iso));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
