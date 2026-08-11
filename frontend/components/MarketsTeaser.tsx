"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { pct } from "@/lib/format";
import {
  formatCompactUsd,
  formatMoverDelta,
  moverTone,
  type MarketMover,
  type MarketStats,
} from "@/lib/marketStats";
import { getMarketsTeaser, pickTopMovers } from "@/lib/marketsTeaser";

type TeaserState = "loading" | "ready" | "error";

const DISCLAIMER = "play money · paper trading · real market prices";

const TONE_CLASS: Record<"pos" | "neg" | "flat", string> = {
  pos: "text-pos",
  neg: "text-neg",
  flat: "text-muted",
};

/**
 * Compact homepage card that surfaces the play-money market: a headline, the
 * active-surface stats, the few biggest 24h movers, and a link into /markets.
 *
 * Live mode fetches client-side via getMarketsTeaser (which reuses the
 * market-stats + movers endpoints); static mode renders the passed-in
 * `stats`/`movers` props baked from the snapshot (no live backend in the Pages
 * demo). Either way the movers are ranked/trimmed through pickTopMovers so the
 * caller can hand over the full baked list.
 *
 * Play money only — real venue prices, virtual ⓥ credits, never real money.
 */
export function MarketsTeaser({
  stats: initialStats = null,
  movers: initialMovers = [],
  n = 3,
}: {
  stats?: MarketStats | null;
  movers?: MarketMover[];
  n?: number;
}) {
  const [stats, setStats] = useState<MarketStats | null>(initialStats);
  const [movers, setMovers] = useState<MarketMover[]>(() => pickTopMovers(initialMovers, n));
  const [state, setState] = useState<TeaserState>(IS_STATIC ? "ready" : "loading");

  useEffect(() => {
    if (IS_STATIC) return; // static demo renders the baked props as-is
    let cancelled = false;
    getMarketsTeaser(n)
      .then(({ stats: s, movers: m }) => {
        if (cancelled) return;
        setStats(s);
        setMovers(m);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [n]);

  return (
    <section className="card p-5" aria-label="Play-money markets">
      <div className="flex items-baseline justify-between gap-3">
        <div className="micro-label">Play-money markets</div>
        <Link href="/markets" className="shrink-0 text-xs font-semibold text-accent hover:underline">
          Trade real events →
        </Link>
      </div>

      <p className="mt-1 text-sm text-ink-2">
        Real events from Polymarket &amp; Kalshi, traded with virtual ⓥ credits — never real money.
      </p>

      {stats && (
        <div className="num mt-2 text-xs text-muted">
          {stats.n_active} active markets · {formatCompactUsd(stats.total_volume_usd)} venue volume
        </div>
      )}

      {state === "loading" && <div className="mt-3 text-sm text-muted">Loading markets…</div>}

      {state === "error" && (
        <div className="mt-3 text-sm text-muted">
          Couldn&apos;t load markets — is the backend running?
        </div>
      )}

      {state === "ready" &&
        (movers.length === 0 ? (
          <div className="mt-3 text-sm text-muted">No notable moves right now.</div>
        ) : (
          <ul className="mt-3 divide-y divide-line/60">
            {movers.map((m) => {
              const tone = moverTone(m.change);
              return (
                <li key={m.event_id}>
                  <Link
                    href={`/markets/${m.event_id}`}
                    className="flex items-center gap-3 py-2 transition-colors hover:text-accent"
                  >
                    <span className={`num shrink-0 text-sm font-bold ${TONE_CLASS[tone]}`}>
                      {formatMoverDelta(m.change)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-2">{m.question}</span>
                    <span className="num shrink-0 text-xs text-muted">{pct(m.yes_price)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        ))}

      <p className="micro-label mt-3">{DISCLAIMER}</p>
    </section>
  );
}
