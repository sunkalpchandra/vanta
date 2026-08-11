"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { pct, signedPct } from "@/lib/format";
import { getTraderKey } from "@/lib/trader";
import { getWatched, isMoved, type WatchItem } from "@/lib/watch";

type ViewState = "loading" | "nokey" | "error" | "ready";

const DISCLAIMER = "play money · paper trading · real market prices";

/**
 * The trader's watched markets and how each moved over the last 24h — a
 * watched-moves digest. Server-truth via lib/watch (GET /api/watch, keyed to
 * the trader's X-API-Key held in this browser), so it needs the client.
 *
 * No identity yet → a "start trading to build a watchlist" CTA. Static demo →
 * an honest no-backend note. Moved markets (isMoved, the same 24h/5-point
 * threshold the backend uses) float to the top and get highlighted. Each row
 * links to the market's own page.
 *
 * Play money only — virtual ⓥ credits, real venue prices, never real money.
 */
export function WatchingList() {
  const [state, setState] = useState<ViewState>("loading");
  const [items, setItems] = useState<WatchItem[]>([]);

  useEffect(() => {
    if (IS_STATIC) return;
    if (getTraderKey() === null) {
      setState("nokey");
      return;
    }
    let cancelled = false;
    getWatched()
      .then((rows) => {
        if (cancelled) return;
        setItems(rows);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (IS_STATIC) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        The static demo has no trading backend, so there is no watchlist to show. Run the backend
        locally to watch markets for 24h price moves.
        <div className="micro-label mt-3">{DISCLAIMER}</div>
      </div>
    );
  }

  if (state === "loading") {
    return <div className="card p-8 text-center text-sm text-muted">Loading your watchlist…</div>;
  }

  if (state === "nokey") {
    return (
      <div className="card p-8 text-center">
        <div className="micro-label">no trader identity yet</div>
        <p className="mt-2 text-sm text-ink-2">
          Start trading to build a watchlist — open any market, tap the ☆ to watch it, and its 24h
          moves show up here.
        </p>
        <Link
          href="/markets"
          className="mt-4 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          Start trading
        </Link>
        <div className="micro-label mt-4">{DISCLAIMER}</div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        Couldn&apos;t load your watchlist — is the backend running?
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="card p-8 text-center">
        <div className="micro-label">nothing watched yet</div>
        <p className="mt-2 text-sm text-ink-2">
          You&apos;re not watching any markets. Open a market and tap the ☆ to track its 24h moves.
        </p>
        <Link
          href="/markets"
          className="mt-4 inline-block rounded-lg border border-line px-4 py-2 text-sm font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
        >
          Browse markets
        </Link>
        <div className="micro-label mt-4">{DISCLAIMER}</div>
      </div>
    );
  }

  // Moved markets first (that's the digest's point), then by move size.
  const rows = [...items].sort((a, b) => {
    const moved = (isMoved(b.delta_24h) ? 1 : 0) - (isMoved(a.delta_24h) ? 1 : 0);
    if (moved !== 0) return moved;
    return Math.abs(b.delta_24h ?? 0) - Math.abs(a.delta_24h ?? 0);
  });
  const movedCount = rows.filter((r) => isMoved(r.delta_24h)).length;

  return (
    <div>
      <div className="micro-label mb-3">
        {rows.length} watched · {movedCount} moved ≥5pts in the last 24h
      </div>
      <div className="card divide-y divide-line/60">
        {rows.map((item) => {
          const moved = isMoved(item.delta_24h);
          return (
            <Link
              key={item.event_id}
              href={`/markets/${item.event_id}`}
              className={`flex items-center gap-3 border-l-2 px-5 py-3 transition-colors hover:bg-surface-2 ${
                moved ? "border-accent" : "border-transparent"
              }`}
            >
              <span className="min-w-0 flex-1 truncate text-sm text-ink">{item.question}</span>
              {moved && (
                <span className="num shrink-0 rounded bg-accent/15 px-2 py-0.5 text-[11px] font-bold uppercase text-accent">
                  moved
                </span>
              )}
              <span className="num shrink-0 text-xs text-muted">
                {item.yes_price !== null ? pct(item.yes_price) : "—"}
              </span>
              <DeltaChip delta={item.delta_24h} />
            </Link>
          );
        })}
      </div>
      <p className="micro-label mt-4">{DISCLAIMER}</p>
    </div>
  );
}

/** Signed 24h delta, coloured by the same rounded whole-percent the label
 * shows (so a "+0%" reads muted, never a contradicting green/red). */
function DeltaChip({ delta }: { delta: number | null }) {
  if (delta == null || !Number.isFinite(delta)) {
    return <span className="num shrink-0 text-xs text-muted">—</span>;
  }
  const pts = Math.round(delta * 100);
  const tone = pts > 0 ? "text-pos" : pts < 0 ? "text-neg" : "text-muted";
  return <span className={`num shrink-0 w-14 text-right text-xs font-bold ${tone}`}>{signedPct(delta)}</span>;
}
