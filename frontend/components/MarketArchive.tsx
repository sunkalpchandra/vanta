"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CATEGORIES } from "@/lib/categories";
import { IS_STATIC } from "@/lib/config";
import { pct, shortDate } from "@/lib/format";
import { compactUsd } from "@/lib/trader";
import {
  getArchive,
  marketCalledIt,
  type ArchiveItem,
  type ArchiveOut,
} from "@/lib/marketArchive";

const PAGE_SIZE = 50;
const CATEGORY_CHIPS = ["all", ...CATEGORIES, "other"] as const;

/** Append a freshly fetched page onto the loaded rows, keyed by event_id.
 * Offset paging over a large table can re-hand rows we already hold; dropping
 * those dupes keeps React keys unique. (Mirrors MarketsBrowser.mergeById.) */
function mergeById(prev: ArchiveItem[], page: ArchiveItem[]): ArchiveItem[] {
  const seen = new Set(prev.map((m) => m.event_id));
  const fresh = page.filter((m) => !seen.has(m.event_id));
  return fresh.length === page.length ? [...prev, ...page] : [...prev, ...fresh];
}

/** Sort resolved rows newest-close first; rows without a close time sink to the
 * end (empty string is the smallest key, so it lands last in descending order). */
function byNewestClose(a: ArchiveItem, b: ArchiveItem): number {
  const ac = a.close_time ?? "";
  const bc = b.close_time ?? "";
  return ac > bc ? -1 : ac < bc ? 1 : 0;
}

/** Settled-markets resolution archive: which real-venue markets resolved, what
 * they settled to, and whether the market's own final price called it. Live
 * mode pages through GET /api/market-archive; the static demo filters the baked
 * sample entirely client-side. */
export function MarketArchive({ sample }: { sample: ArchiveOut }) {
  const [category, setCategory] = useState<string>("all");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<ArchiveItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(!IS_STATIC);
  const [error, setError] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);

  // Changing the category restarts pagination from the top.
  function applyFilter(fn: () => void) {
    fn();
    setOffset(0);
  }

  // Re-attempt the same offset after a failed load-more without disturbing the
  // rows already on screen (bumping the nonce re-runs the fetch effect).
  const retryLoadMore = () => setReloadNonce((n) => n + 1);

  useEffect(() => {
    if (IS_STATIC) return;
    let cancelled = false;
    const isInitial = offset === 0;
    setLoading(true);
    // A fresh (offset 0) fetch owns the full-width error; a later page owns only
    // the inline load-more error, so its failure never blanks the loaded rows.
    if (isInitial) setError(false);
    setLoadMoreError(false);
    getArchive({ category, limit: PAGE_SIZE, offset })
      .then((page) => {
        if (cancelled) return;
        setTotal(page.total);
        setItems((prev) => (isInitial ? page.items : mergeById(prev, page.items)));
        setError(false);
        setLoadMoreError(false);
      })
      .catch(() => {
        if (cancelled) return;
        if (isInitial) setError(true);
        else setLoadMoreError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [category, offset, reloadNonce]);

  const staticVisible = useMemo(() => {
    if (!IS_STATIC) return [];
    const rows = sample.items.filter((m) => category === "all" || m.category === category);
    return [...rows].sort(byNewestClose);
  }, [sample, category]);

  const visible = IS_STATIC ? staticVisible : items;
  const shownTotal = IS_STATIC ? staticVisible.length : total;

  return (
    <div>
      {IS_STATIC && (
        <div className="card mb-5 px-4 py-3 text-xs text-muted">
          static demo — sample of the settled corpus; run the backend for the full resolution archive
        </div>
      )}
      <div role="group" aria-label="Filter by category" className="mb-5 flex flex-wrap gap-2">
        {CATEGORY_CHIPS.map((c) => (
          <button
            key={c}
            onClick={() => applyFilter(() => setCategory(c))}
            aria-pressed={category === c}
            className={`micro-label rounded-full border px-3 py-1.5 transition-colors ${
              category === c
                ? "border-accent !text-accent"
                : "border-line !text-ink-2 hover:border-accent/50"
            }`}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="micro-label mb-3">
        {shownTotal} settled market{shownTotal === 1 ? "" : "s"}
        {IS_STATIC ? " in the sample" : ""}
      </div>
      {error && !IS_STATIC ? (
        <div className="card p-8 text-center text-sm text-muted">
          Couldn&apos;t load the archive — is the backend running?
        </div>
      ) : visible.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          {loading ? "Loading archive…" : "Nothing has resolved yet."}
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="micro-label px-5 py-3 font-normal">Question</th>
                <th className="micro-label px-5 py-3 font-normal">Category</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Final price</th>
                <th className="micro-label px-5 py-3 text-center font-normal">Outcome</th>
                <th className="micro-label px-5 py-3 text-center font-normal">Called it</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Closed</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((m) => (
                <ArchiveRow key={m.event_id} market={m} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!IS_STATIC && !error && items.length < total && (
        <div className="mt-4 text-center">
          {loadMoreError ? (
            <div
              role="alert"
              className="inline-flex items-center gap-3 rounded-lg border border-line px-4 py-2 text-xs"
            >
              <span className="text-muted">Couldn&apos;t load more.</span>
              <button
                onClick={retryLoadMore}
                disabled={loading}
                className="font-semibold text-accent transition-colors hover:text-ink disabled:opacity-50"
              >
                {loading ? "Retrying…" : "Retry"}
              </button>
            </div>
          ) : (
            <button
              onClick={() => setOffset(items.length)}
              disabled={loading}
              className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
            >
              {loading ? "Loading…" : `Load more (${items.length} of ${total})`}
            </button>
          )}
        </div>
      )}
      <p className="micro-label mt-6">
        &ldquo;Called it&rdquo; compares the market&apos;s own final price against the realized
        outcome — a final YES price above 50% is the market leaning YES. play money · paper trading ·
        real market prices
      </p>
    </div>
  );
}

function ArchiveRow({ market }: { market: ArchiveItem }) {
  const called = marketCalledIt(market);
  return (
    <tr className="border-b border-line/60 last:border-0">
      <td className="max-w-md px-5 py-3">
        <Link href={`/markets/${market.event_id}`} className="text-ink hover:text-accent">
          {market.question}
        </Link>
        <div className="micro-label mt-1 opacity-70">{market.source}</div>
      </td>
      <td className="px-5 py-3 capitalize text-ink-2">{market.category}</td>
      <td className="num px-5 py-3 text-right text-ink-2">
        {market.final_price !== null ? pct(market.final_price) : "—"}
      </td>
      <td className="px-5 py-3 text-center">
        <OutcomeChip outcome={market.outcome} />
      </td>
      <td className="px-5 py-3 text-center">
        <CalledIt called={called} />
      </td>
      <td className="num px-5 py-3 text-right text-ink-2">
        {market.close_time ? shortDate(market.close_time) : "—"}
      </td>
    </tr>
  );
}

function OutcomeChip({ outcome }: { outcome: number | null }) {
  if (outcome === null) return <span className="text-muted">—</span>;
  const yes = outcome === 1;
  return (
    <span
      className={`num rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
        yes ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
      }`}
    >
      {yes ? "yes" : "no"}
    </span>
  );
}

/** ✓ (market agreed with reality) / ✗ (it didn't) / — (undecidable). */
function CalledIt({ called }: { called: boolean | null }) {
  if (called === null) return <span className="text-muted" title="no final price recorded">—</span>;
  return called ? (
    <span className="font-bold text-pos" title="the market's final price matched the outcome">
      ✓
    </span>
  ) : (
    <span className="font-bold text-neg" title="the market's final price missed the outcome">
      ✗
    </span>
  );
}
