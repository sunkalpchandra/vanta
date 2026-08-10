import { notFound } from "next/navigation";
import { MarketDetail } from "@/components/MarketDetail";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { getMarketsSample, getMarketPriceHistory } from "@/lib/data";
import { buildPriceSeries } from "@/lib/marketDetail";
import { pct } from "@/lib/format";
import type { MarketItem } from "@/lib/trader";

// SSR reaches the API by its internal route inside docker compose; the browser
// never uses this (server-only, same pattern as lib/data.ts).
const SSR_API_URL = process.env.API_URL_INTERNAL ?? API_URL;

/** Load one market. Static mode reads it from the baked sample; live mode hits
 * GET /api/markets/{id} (which returns a MarketDetail — a superset of the
 * MarketItem fields this page renders). Returns null when absent/offline. */
async function loadMarket(id: string): Promise<MarketItem | null> {
  if (IS_STATIC) {
    const sample = await getMarketsSample();
    if (!sample) return null;
    const all = [...(sample.active ?? []), ...(sample.settled ?? [])];
    return all.find((m) => String(m.id) === id) ?? null;
  }
  try {
    const res = await fetch(`${SSR_API_URL}/api/markets/${id}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as MarketItem;
  } catch {
    return null; // backend offline — page renders notFound()
  }
}

export async function generateStaticParams() {
  // Static demo: prerender every sampled market id. Live mode: render on demand.
  if (!IS_STATIC) return [];
  const sample = await getMarketsSample();
  if (!sample) return [];
  const all = [...(sample.active ?? []), ...(sample.settled ?? [])];
  return all.map((m) => ({ id: String(m.id) }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const market = await loadMarket(id);
  if (!market) return { title: "market not found — vanta" };
  const price = market.yes_price !== null ? ` — YES ${pct(market.yes_price)}` : "";
  return {
    title: `${market.question} — vanta`,
    description: `Play-money market on ${market.source}${price}. play money · paper trading · real market prices.`,
  };
}

export default async function MarketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const market = await loadMarket(id);
  if (!market) notFound();
  const rows = buildPriceSeries(await getMarketPriceHistory(id));
  return (
    <div className="mx-auto max-w-3xl">
      <MarketDetail market={market} initialRows={rows} />
    </div>
  );
}
