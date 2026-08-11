// Category browsing for the play-money markets surface. Pure bucketing helpers
// (used by the static demo and unit-tested here) plus a client-side fetcher for
// live mode. Client components may import this — it only reaches lib/api.ts for
// API_URL, never lib/data.ts (which reads the filesystem).

import { API_URL } from "./api";
import { CATEGORIES } from "./categories";
import type { MarketItem } from "./trader";

// The browsable category slugs: the six curated categories plus the "other"
// bucket the backend normalizer emits for everything else. Typed as a plain
// string[] so `.includes(someString)` and iteration stay ergonomic.
export const MARKET_CATEGORY_SLUGS: readonly string[] = [...CATEGORIES, "other"];

const KNOWN: ReadonlySet<string> = new Set(CATEGORIES);

/** The bucket slug an item belongs to: its category when that's one of the six
 * curated categories, else "other". Mirrors the backend normalizer, which only
 * ever stores one of the six or the literal "other" — so anything unrecognized
 * collapses into "other" here too, keeping the buckets a clean partition. */
function bucketOf(category: string): string {
  return KNOWN.has(category) ? category : "other";
}

/** The items whose category bucket is `slug`. A known category matches items
 * with exactly that category; "other" collects the literal "other" plus any
 * unrecognized category. An unknown slug matches nothing. Never mutates input. */
export function filterByCategory(items: MarketItem[], slug: string): MarketItem[] {
  return items.filter((m) => bucketOf(m.category) === slug);
}

/** Count of items per category bucket, sparse — only buckets that occur appear,
 * so `Object.values(...)` sums to `items.length`. Consumers default absent
 * slugs to 0. */
export function categoryCounts(items: MarketItem[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const m of items) {
    const bucket = bucketOf(m.category);
    counts[bucket] = (counts[bucket] ?? 0) + 1;
  }
  return counts;
}

type MarketsListBody = MarketItem[] | { items?: MarketItem[] };

/** Live-mode fetch of the top active markets in one category, by volume. Throws
 * on a non-OK response so callers can tell "backend down" from "no markets".
 * `fetchImpl` is injectable for tests; production passes the global fetch. */
export async function getCategoryMarkets(
  slug: string,
  fetchImpl: typeof fetch = fetch,
): Promise<MarketItem[]> {
  const params = new URLSearchParams({
    status: "active",
    category: slug,
    sort: "volume",
    limit: "100",
  });
  const res = await fetchImpl(`${API_URL}/api/markets?${params.toString()}`);
  if (!res.ok) throw new Error(`markets fetch failed (${res.status})`);
  const body = (await res.json()) as MarketsListBody;
  return Array.isArray(body) ? body : (body.items ?? []);
}
