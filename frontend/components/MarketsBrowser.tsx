"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_URL } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { IS_STATIC } from "@/lib/config";
import { pct, shortDate } from "@/lib/format";
import { compactUsd, daysUntilClose, type MarketItem, type MarketsOut } from "@/lib/trader";
import { TradeTicket } from "./TradeTicket";

type Tab = "active" | "settled";
type MarketSort = "volume" | "close_time";

const PAGE_SIZE = 50;
const CATEGORY_CHIPS = ["all", ...CATEGORIES, "other"] as const;

/** Append a freshly fetched page onto the loaded rows, keyed by id.
 * Offset paging over a live, re-sorted server table can re-hand rows we
 * already hold; dropping those dupes keeps React keys unique and stops the
 * same market appearing twice. */
function mergeById(prev: MarketItem[], page: MarketItem[]): MarketItem[] {
  const seen = new Set(prev.map((m) => m.id));
  const fresh = page.filter((m) => !seen.has(m.id));
  return fresh.length === page.length ? [...prev, ...page] : [...prev, ...fresh];
}

/** Browse the real-event corpus (Polymarket + Kalshi) and trade inline.
 * Live mode pages through GET /api/markets; the static demo filters the
 * baked sample entirely client-side. */
export function MarketsBrowser({ sample }: { sample: MarketsOut }) {
  const [tab, setTab] = useState<Tab>("active");
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<MarketSort>("volume");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<MarketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(!IS_STATIC);
  const [error, setError] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);

  // Any filter change restarts pagination and collapses the open row.
  function applyFilter(fn: () => void) {
    fn();
    setOffset(0);
    setOpenId(null);
  }

  // Re-attempt the same offset after a failed load-more, leaving the rows
  // already on screen untouched (bumping the nonce re-runs the fetch effect).
  const retryLoadMore = () => setReloadNonce((n) => n + 1);

  useEffect(() => {
    if (IS_STATIC) return;
    let cancelled = false;
    const isInitial = offset === 0;
    setLoading(true);
    // A fresh (offset 0) fetch owns the full-width error; a later page owns
    // only the inline load-more error, so its failure never blanks the rows
    // already on screen. Clear both before every attempt.
    if (isInitial) setError(false);
    setLoadMoreError(false);
    const params = new URLSearchParams({
      status: tab,
      sort,
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    if (category !== "all") params.set("category", category);
    if (query.trim()) params.set("q", query.trim());
    // Small debounce so typing in search doesn't spam the API.
    const timer = setTimeout(
      () => {
        fetch(`${API_URL}/api/markets?${params}`)
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
          .then((page: MarketsOut) => {
            if (cancelled) return;
            setTotal(page.total);
            // Replace on a fresh page; otherwise append deduped by id — offset
            // paging over a re-sorted table can re-hand rows we already hold.
            setItems((prev) => (isInitial ? page.items : mergeById(prev, page.items)));
            setError(false);
            setLoadMoreError(false);
          })
          .catch(() => {
            if (cancelled) return;
            // A later-page failure keeps the loaded rows and surfaces an inline
            // retry; only a first page (nothing to preserve) blanks to error.
            if (isInitial) setError(true);
            else setLoadMoreError(true);
          })
          .finally(() => {
            if (!cancelled) setLoading(false);
          });
      },
      query ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [tab, category, query, sort, offset, reloadNonce]);

  const staticVisible = useMemo(() => {
    if (!IS_STATIC) return [];
    const needle = query.trim().toLowerCase();
    const rows = sample.items.filter((m) => {
      if (tab === "active" ? m.outcome !== null : m.outcome === null) return false;
      if (category !== "all" && m.category !== category) return false;
      if (needle && !m.question.toLowerCase().includes(needle)) return false;
      return true;
    });
    return rows.sort((a, b) =>
      sort === "volume"
        ? b.volume_usd - a.volume_usd
        : // soonest close first; unknown closes sink to the bottom
          (a.close_time ?? "9999") < (b.close_time ?? "9999")
          ? -1
          : 1,
    );
  }, [sample, tab, category, query, sort]);

  const visible = IS_STATIC ? staticVisible : items;
  const shownTotal = IS_STATIC ? staticVisible.length : total;

  return (
    <div>
      {IS_STATIC && (
        <div className="card mb-5 px-4 py-3 text-xs text-muted">
          static demo — sample of the live corpus; run the backend for all 100k+ events and live
          trading
        </div>
      )}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div
          role="group"
          aria-label="Market status"
          className="inline-flex overflow-hidden rounded-lg border border-line"
        >
          {(["active", "settled"] as const).map((t) => (
            <button
              key={t}
              onClick={() => applyFilter(() => setTab(t))}
              aria-pressed={tab === t}
              className={`px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                tab === t ? "bg-surface-2 text-accent" : "text-ink-2 hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="ml-auto flex w-full items-center gap-2 sm:w-auto">
          <select
            value={sort}
            onChange={(e) => applyFilter(() => setSort(e.target.value as MarketSort))}
            aria-label="Sort markets"
            className="micro-label rounded-full border border-line bg-surface-2 px-3 py-1.5 !text-ink-2 outline-none focus:border-accent"
          >
            <option value="volume">by volume</option>
            <option value="close_time">by close time</option>
          </select>
          <input
            type="search"
            value={query}
            onChange={(e) => applyFilter(() => setQuery(e.target.value))}
            placeholder="Search markets…"
            aria-label="Search markets"
            className="w-full rounded-full border border-line bg-surface-2 px-4 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent sm:w-52"
          />
        </div>
      </div>
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
        {shownTotal} {tab} market{shownTotal === 1 ? "" : "s"}
        {IS_STATIC ? " in the sample" : ""}
      </div>
      {error && !IS_STATIC ? (
        <div className="card p-8 text-center text-sm text-muted">
          Couldn&apos;t load markets — is the backend running?
        </div>
      ) : visible.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          {loading ? "Loading markets…" : "No markets match."}
        </div>
      ) : (
        <div className="card divide-y divide-line/60">
          {visible.map((m) => (
            <MarketRow
              key={m.id}
              market={m}
              open={openId === m.id}
              onToggle={() => setOpenId(openId === m.id ? null : m.id)}
            />
          ))}
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
      <p className="micro-label mt-6">play money · paper trading · real market prices</p>
    </div>
  );
}

function MarketRow({
  market,
  open,
  onToggle,
}: {
  market: MarketItem;
  open: boolean;
  onToggle: () => void;
}) {
  const settled = market.outcome !== null;
  const days = daysUntilClose(market.close_time);
  return (
    <div>
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 text-left transition-colors hover:bg-surface-2/60"
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
            {settled ? (
              <OutcomeChip outcome={market.outcome ?? 0} />
            ) : (
              <>
                <div className="micro-label">closes</div>
                <div className="num text-sm text-ink-2">
                  {days === null ? "—" : days === 0 ? "today" : `${days}d`}
                </div>
              </>
            )}
          </div>
        </div>
      </button>
      {open && (
        <div className="border-t border-line/60 bg-surface-2/40 px-5 py-4">
          {settled ? <SettledSummary market={market} /> : <TradeTicket market={market} />}
          <Link
            href={`/markets/${market.id}`}
            className="micro-label mt-3 inline-block !text-accent hover:underline"
          >
            price history &amp; details →
          </Link>
        </div>
      )}
    </div>
  );
}

function OutcomeChip({ outcome }: { outcome: number }) {
  const yes = outcome === 1;
  return (
    <span
      className={`num rounded px-2 py-0.5 text-xs font-bold ${
        yes ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
      }`}
    >
      {yes ? "YES" : "NO"}
    </span>
  );
}

function SettledSummary({ market }: { market: MarketItem }) {
  return (
    <div className="text-sm text-ink-2">
      <div className="flex flex-wrap items-center gap-3">
        <OutcomeChip outcome={market.outcome ?? 0} />
        <span>
          Settled {market.outcome === 1 ? "YES" : "NO"} at the venue ·{" "}
          {compactUsd(market.volume_usd)} traded
          {market.close_time ? ` · closed ${shortDate(market.close_time)}` : ""}
        </span>
      </div>
      <p className="micro-label mt-2">settled markets are read-only — positions paid at the venue outcome</p>
    </div>
  );
}
