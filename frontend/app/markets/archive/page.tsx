import Link from "next/link";
import { MarketArchive } from "@/components/MarketArchive";
import { IS_STATIC } from "@/lib/config";
import type { ArchiveOut } from "@/lib/marketArchive";

export const metadata = { title: "settled markets — archive — vanta" };

const EMPTY: ArchiveOut = { total: 0, items: [] };

// The canonical static reader (data.getMarketArchiveSample) lands with
// integration — the exporter must bake market-archive.json and lib/data.ts must
// add the getter + a lockstep entry. Until then this server component reads the
// baked file directly (static mode only). Live mode pages through the API from
// the client, so the server hands down an empty sample.
async function loadSample(): Promise<ArchiveOut> {
  if (!IS_STATIC) return EMPTY;
  try {
    const { promises: fs } = await import("fs");
    const { join } = await import("path");
    const file = join(process.cwd(), "public", "data", "market-archive.json");
    return JSON.parse(await fs.readFile(file, "utf8")) as ArchiveOut;
  } catch {
    return EMPTY; // file not baked yet — the page renders its empty state
  }
}

export default async function MarketArchivePage() {
  const sample = await loadSample();
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Settled markets — resolution archive</h1>
        <p className="mt-1 text-sm text-ink-2">
          Every real-venue market that has resolved, what it settled to, and whether the market&apos;s
          own final price called it — play money · paper trading · real market prices.
        </p>
        <Link
          href="/markets"
          className="micro-label mt-3 inline-block !text-accent hover:underline"
        >
          ← back to live markets
        </Link>
      </div>
      <MarketArchive sample={sample} />
    </div>
  );
}
