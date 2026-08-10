"use client";

import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { formatCompactUsd, getMarketStats, type MarketStats } from "@/lib/marketStats";
import { StatTile } from "./StatTile";

type BarState = "loading" | "ready" | "empty" | "error";

/**
 * Market-surface stat tiles: active/settled counts, per-venue breakdown, total
 * volume, and participation (traders / open positions / trades). Live mode
 * fetches client-side from /api/market-stats; static mode renders the passed-in
 * `stats` prop from the baked snapshot (no live backend in the Pages demo).
 * Presentational placement is wired separately.
 *
 * Play money only — the tiles describe a paper-trading surface over real venue
 * prices; nothing here is real money.
 */
export function MarketStatsBar({ stats: initial = null }: { stats?: MarketStats | null }) {
  const [stats, setStats] = useState<MarketStats | null>(IS_STATIC ? initial : null);
  const [state, setState] = useState<BarState>(
    IS_STATIC ? (initial ? "ready" : "empty") : "loading",
  );

  useEffect(() => {
    if (IS_STATIC) return;
    let cancelled = false;
    getMarketStats()
      .then((s) => {
        if (cancelled) return;
        setStats(s);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return <div className="card px-5 py-4 text-sm text-muted">Loading market stats…</div>;
  }
  if (state === "error") {
    return (
      <div className="card px-5 py-4 text-sm text-muted">
        Couldn&apos;t load market stats — is the backend running?
      </div>
    );
  }
  if (state === "empty" || !stats) {
    return <div className="card px-5 py-4 text-sm text-muted">No market data yet.</div>;
  }

  const { by_source } = stats;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Market surface stats">
      <StatTile
        label="Active markets"
        value={String(stats.n_active)}
        href="/markets"
        sub={`polymarket ${by_source.polymarket} · kalshi ${by_source.kalshi} · manifold ${by_source.manifold}`}
      />
      <StatTile
        label="Settled markets"
        value={String(stats.n_settled)}
        sub="resolved on the venue"
      />
      <StatTile
        label="Total volume"
        value={formatCompactUsd(stats.total_volume_usd)}
        tone="accent"
        sub="real venue volume (USD)"
      />
      <StatTile
        label="Traders"
        value={String(stats.n_traders)}
        sub={`${stats.n_open_positions} open positions · ${stats.n_trades} trades`}
      />
    </div>
  );
}
