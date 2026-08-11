"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { pct } from "@/lib/format";
import {
  highlightMatch,
  MIN_QUERY_LEN,
  searchMarkets,
  searchSample,
  type SearchHit,
  type SearchStatus,
} from "@/lib/marketSearch";
import type { MarketItem } from "@/lib/types";

const STATUSES: SearchStatus[] = ["active", "settled", "all"];
const LIMIT = 50;

/** Global market search. Live mode debounces GET /api/market-search; the static
 * demo filters the baked markets-sample (passed as a prop from the server
 * shell) entirely client-side, so the demo never needs a backend. */
export function MarketSearch({ sample }: { sample: MarketItem[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<SearchStatus>("active");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const trimmed = query.trim();
  const hasQuery = trimmed.length >= MIN_QUERY_LEN;
  const tooShort = trimmed.length > 0 && !hasQuery;

  // Static demo: filter the baked sample client-side (no API). Recomputes only
  // when the query, status, or sample change.
  const staticHits = useMemo(
    () => (IS_STATIC ? searchSample(sample, trimmed, status, LIMIT) : []),
    [sample, trimmed, status],
  );

  // Live mode: debounced fetch so typing doesn't spam the API. Static mode does
  // no I/O — this effect is a no-op there.
  useEffect(() => {
    if (IS_STATIC) return;
    if (!hasQuery) {
      setResults([]);
      setError(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(false);
    const timer = setTimeout(() => {
      searchMarkets(trimmed, status)
        .then((hits) => {
          if (!cancelled) setResults(hits);
        })
        .catch(() => {
          if (cancelled) return;
          setResults([]);
          setError(true);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [trimmed, status, hasQuery]);

  const hits = IS_STATIC ? staticHits : results;

  return (
    <div>
      {IS_STATIC && (
        <div className="card mb-5 px-4 py-3 text-xs text-muted">
          static demo — searching the baked sample only; run the backend to search all 100k+ events
        </div>
      )}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div
          role="group"
          aria-label="Market status"
          className="inline-flex overflow-hidden rounded-lg border border-line"
        >
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              aria-pressed={status === s}
              className={`px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                status === s ? "bg-surface-2 text-accent" : "text-ink-2 hover:text-ink"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="ml-auto w-full sm:w-auto">
          {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search real-event markets…"
            aria-label="Search markets"
            className="w-full rounded-full border border-line bg-surface-2 px-4 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent sm:w-72"
          />
        </div>
      </div>

      {!hasQuery ? (
        <div className="card p-8 text-center text-sm text-muted">
          {tooShort
            ? `Keep typing — at least ${MIN_QUERY_LEN} characters.`
            : "Search real-venue markets by keyword — try a name, ticker, or topic."}
        </div>
      ) : error ? (
        <div className="card p-8 text-center text-sm text-muted">
          Couldn&apos;t search markets — is the backend running?
        </div>
      ) : loading && hits.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">Searching…</div>
      ) : hits.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No markets match “{trimmed}”.
        </div>
      ) : (
        <>
          <div className="micro-label mb-3">
            {hits.length} result{hits.length === 1 ? "" : "s"}
            {IS_STATIC ? " in the sample" : ""}
          </div>
          <div className="card divide-y divide-line/60">
            {hits.map((hit) => (
              <SearchResultRow key={hit.event_id} hit={hit} query={trimmed} />
            ))}
          </div>
        </>
      )}

      <p className="micro-label mt-6">play money · paper trading · real market prices</p>
    </div>
  );
}

function SearchResultRow({ hit, query }: { hit: SearchHit; query: string }) {
  const settled = hit.outcome !== null;
  return (
    <Link
      href={`/markets/${hit.event_id}`}
      className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-surface-2/60"
    >
      <div className="min-w-0 flex-1 basis-64">
        <div className="text-sm font-medium leading-snug text-ink">
          {highlightMatch(hit.question, query).map((part, i) =>
            part.match ? (
              <mark key={i} className="rounded bg-accent/25 px-0.5 font-semibold text-ink">
                {part.text}
              </mark>
            ) : (
              <span key={i}>{part.text}</span>
            ),
          )}
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="micro-label">{hit.category}</span>
          <span className="micro-label opacity-70">{hit.source}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-5">
        <div className="w-14 text-right">
          <div className="micro-label">yes</div>
          <div className="num text-lg font-bold text-accent">
            {hit.yes_price !== null ? pct(hit.yes_price) : "—"}
          </div>
        </div>
        <div className="w-16 text-right">
          {settled ? (
            <span
              className={`num rounded px-2 py-0.5 text-xs font-bold ${
                hit.outcome === 1 ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
              }`}
            >
              {hit.outcome === 1 ? "YES" : "NO"}
            </span>
          ) : (
            <span className="micro-label">{hit.active ? "active" : "closed"}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
