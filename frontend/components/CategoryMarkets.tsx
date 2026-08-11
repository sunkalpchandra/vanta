"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { getCategoryMarkets } from "@/lib/marketCategories";
import { pct } from "@/lib/format";
import { compactUsd, daysUntilClose, type MarketItem } from "@/lib/trader";

/** Rows of active markets in one category. Static mode renders the server-passed
 * `initial` list as-is; live mode ignores it and fetches the category from the
 * API on mount (and whenever the slug changes). Each row links to the market's
 * detail page with an ABSOLUTE href so the /vanta basePath isn't doubled. */
export function CategoryMarkets({ slug, initial }: { slug: string; initial: MarketItem[] }) {
  const [items, setItems] = useState<MarketItem[]>(initial);
  const [loading, setLoading] = useState(!IS_STATIC);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (IS_STATIC) return; // static demo: `initial` is already the full sample
    let cancelled = false;
    setLoading(true);
    setError(false);
    getCategoryMarkets(slug)
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (error && !IS_STATIC) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        Couldn&apos;t load markets — is the backend running?
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        {loading ? "Loading markets…" : `No active markets in ${slug} right now.`}
      </div>
    );
  }

  return (
    <div>
      <div className="micro-label mb-3">
        {items.length} active market{items.length === 1 ? "" : "s"}
      </div>
      <div className="card divide-y divide-line/60">
        {items.map((m) => (
          <CategoryMarketRow key={m.id} market={m} />
        ))}
      </div>
      <p className="micro-label mt-6">play money · paper trading · real market prices</p>
    </div>
  );
}

function CategoryMarketRow({ market }: { market: MarketItem }) {
  const days = daysUntilClose(market.close_time);
  return (
    <Link
      href={`/markets/${market.id}`}
      className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-surface-2/60"
    >
      <div className="min-w-0 flex-1 basis-64">
        <div className="text-sm font-medium leading-snug text-ink">{market.question}</div>
        <div className="mt-1 flex items-center gap-2">
          <span className="micro-label">{market.category}</span>
          <span className="micro-label opacity-70">{market.source}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-5">
        <div className="w-14 text-right">
          <div className="micro-label">yes</div>
          <div className="num text-lg font-bold text-accent">
            {market.yes_price !== null ? pct(market.yes_price) : "—"}
          </div>
        </div>
        <div className="hidden w-16 text-right sm:block">
          <div className="micro-label">vol</div>
          <div className="num text-sm text-ink-2">{compactUsd(market.volume_usd)}</div>
        </div>
        <div className="w-20 text-right">
          <div className="micro-label">closes</div>
          <div className="num text-sm text-ink-2">
            {days === null ? "—" : days === 0 ? "today" : `${days}d`}
          </div>
        </div>
      </div>
    </Link>
  );
}
