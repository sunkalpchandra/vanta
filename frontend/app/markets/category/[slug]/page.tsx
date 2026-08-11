import Link from "next/link";
import { notFound } from "next/navigation";
import { CategoryMarkets } from "@/components/CategoryMarkets";
import { IS_STATIC } from "@/lib/config";
import { getMarketsSample } from "@/lib/data";
import { filterByCategory, MARKET_CATEGORY_SLUGS } from "@/lib/marketCategories";
import type { MarketItem } from "@/lib/trader";

// Prerender the six curated categories + "other". A small fixed set, so we
// enumerate it in both modes; live mode still renders the rows client-side.
export function generateStaticParams() {
  return MARKET_CATEGORY_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!MARKET_CATEGORY_SLUGS.includes(slug)) return { title: "category not found — vanta" };
  return { title: `${slug} markets — vanta` };
}

/** The category's active markets for the initial render. Static mode filters
 * the baked sample; live mode passes an empty list — CategoryMarkets fetches
 * the category itself on mount. */
async function loadInitial(slug: string): Promise<MarketItem[]> {
  if (!IS_STATIC) return [];
  const sample = await getMarketsSample();
  if (!sample) return [];
  return filterByCategory(sample.active ?? [], slug);
}

export default async function MarketCategoryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  if (!MARKET_CATEGORY_SLUGS.includes(slug)) notFound();
  const initial = await loadInitial(slug);

  return (
    <div>
      <div className="mb-8">
        <div className="micro-label">markets · category</div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          <span className="capitalize">{slug}</span> markets
        </h1>
        <p className="mt-1 text-sm text-ink-2">
          Real events synced from Polymarket &amp; Kalshi, traded with virtual ⓥ credits —
          play money · paper trading · real market prices.
        </p>
      </div>
      <CategoryMarkets slug={slug} initial={initial} />
      <div className="mt-8">
        <Link href="/markets" className="text-sm text-accent hover:underline">
          ← All markets
        </Link>
      </div>
    </div>
  );
}
