import { MarketsBrowser } from "@/components/MarketsBrowser";
import { IS_STATIC } from "@/lib/config";
import * as data from "@/lib/data";
import type { MarketsOut } from "@/lib/trader";

export const metadata = { title: "markets — vanta" };

const EMPTY: MarketsOut = { total: 0, items: [] };

// The canonical sample getter (getMarketsSample) lives in lib/data.ts, a
// shared file that lands with integration. Until it exists, fall back to
// reading the baked snapshot directly — same file, same shape — so the
// static demo works either way. Live mode never needs the sample: the
// browser pages through /api/markets itself.
async function loadSample(): Promise<MarketsOut> {
  const getter = (data as unknown as { getMarketsSample?: () => Promise<MarketsOut | null> })
    .getMarketsSample;
  if (getter) return (await getter()) ?? EMPTY;
  if (!IS_STATIC) return EMPTY;
  try {
    const { promises: fs } = await import("fs");
    const { join } = await import("path");
    const file = join(process.cwd(), "public", "data", "markets-sample.json");
    return JSON.parse(await fs.readFile(file, "utf8")) as MarketsOut;
  } catch {
    return EMPTY;
  }
}

export default async function MarketsIndexPage() {
  const sample = await loadSample();
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Markets — real events, live prices</h1>
        <p className="mt-1 text-sm text-ink-2">
          Events synced from Polymarket &amp; Kalshi, traded with virtual ⓥ credits —
          play money · paper trading · real market prices.
        </p>
      </div>
      <MarketsBrowser sample={sample} />
    </div>
  );
}
