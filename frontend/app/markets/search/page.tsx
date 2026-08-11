import { MarketSearch } from "@/components/MarketSearch";
import { IS_STATIC } from "@/lib/config";
import { getMarketsSample } from "@/lib/data";
import type { MarketItem } from "@/lib/types";

export const metadata = { title: "search markets — vanta" };

// Static demo searches the baked markets-sample client-side; live mode hits the
// API. Only static mode needs the sample, so live builds skip the two-fetch
// getMarketsSample entirely (same guard as markets/page.tsx). data.ts is a
// server-only module — read here in the server shell, hand the flat list down.
async function loadSample(): Promise<MarketItem[]> {
  if (!IS_STATIC) return [];
  const sample = await getMarketsSample();
  if (!sample) return [];
  return [...(sample.active ?? []), ...(sample.settled ?? [])];
}

export default async function MarketSearchPage() {
  const sample = await loadSample();
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Search markets</h1>
        <p className="mt-1 text-sm text-ink-2">
          Find real-venue events by keyword across Polymarket &amp; Kalshi — traded with virtual ⓥ
          credits. Play money · paper trading · real market prices.
        </p>
      </div>
      <MarketSearch sample={sample} />
    </div>
  );
}
