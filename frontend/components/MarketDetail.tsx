"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CategoryBadge } from "@/components/Badges";
import { MarketPriceChart } from "@/components/MarketPriceChart";
import { StatTile } from "@/components/StatTile";
import { TradeTicket } from "@/components/TradeTicket";
import { IS_STATIC } from "@/lib/config";
import { pct, shortDate } from "@/lib/format";
import { getMarketHistory, type PriceRow } from "@/lib/marketDetail";
import { compactUsd, daysUntilClose, type MarketItem } from "@/lib/trader";

const PLAY_MONEY_LINE = "play money · paper trading · real market prices";

// Static export ships no per-market price history (it would need matching
// snapshot entries), so mark that mode explicitly rather than firing a fetch at
// a backend that isn't there.
type HistoryState =
  | { status: "loading" }
  | { status: "ready"; rows: PriceRow[] }
  | { status: "error" }
  | { status: "static" };

function closesLabel(days: number | null): string {
  if (days === null) return "—";
  return days === 0 ? "today" : `${days}d`;
}

function OutcomeChip({ outcome }: { outcome: number }) {
  const yes = outcome === 1;
  return (
    <span
      className={`num rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
        yes ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
      }`}
    >
      settled {yes ? "yes" : "no"}
    </span>
  );
}

function ChartArea({ history }: { history: HistoryState }) {
  if (history.status === "ready" && history.rows.length > 0) {
    return <MarketPriceChart rows={history.rows} />;
  }
  const message =
    history.status === "loading"
      ? "Loading price history…"
      : history.status === "error"
        ? "Couldn't load price history — is the backend running?"
        : history.status === "static"
          ? "Price history isn't included in the static demo — run the backend for the synced series."
          : "No synced price history yet for this market.";
  return (
    <div className="flex h-56 items-center justify-center px-4 text-center text-sm text-muted">
      {message}
    </div>
  );
}

function SettledSummary({ market }: { market: MarketItem }) {
  const yes = market.outcome === 1;
  return (
    <div className="text-sm text-ink-2">
      <div className="flex flex-wrap items-center gap-3">
        <OutcomeChip outcome={market.outcome ?? 0} />
        <span>
          Resolved {yes ? "YES" : "NO"} at the venue · {compactUsd(market.volume_usd)} traded
          {market.close_time ? ` · closed ${shortDate(market.close_time)}` : ""}
        </span>
      </div>
      <p className="micro-label mt-3">
        settled markets are read-only — positions paid at the venue outcome
      </p>
    </div>
  );
}

/** Detail view for one real-event market: header + synced YES-price chart, then
 * the inline trade ticket (active) or the settlement summary (resolved).
 * History is fetched client-side on mount. */
export function MarketDetail({ market, initialRows }: { market: MarketItem; initialRows?: PriceRow[] }) {
  const [history, setHistory] = useState<HistoryState>(
    initialRows && initialRows.length > 0
      ? { status: "ready", rows: initialRows }
      : IS_STATIC
        ? { status: "static" }
        : { status: "loading" },
  );

  useEffect(() => {
    if (IS_STATIC) {
      setHistory(
        initialRows && initialRows.length > 0 ? { status: "ready", rows: initialRows } : { status: "static" },
      );
      return;
    }
    let cancelled = false;
    setHistory({ status: "loading" });
    getMarketHistory(market.id)
      .then((rows) => {
        if (!cancelled) setHistory({ status: "ready", rows });
      })
      .catch(() => {
        if (!cancelled) setHistory({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [market.id]);

  const settled = market.outcome !== null;
  const days = daysUntilClose(market.close_time);

  return (
    <div>
      <Link href="/markets" className="text-sm text-accent hover:underline">
        ← All markets
      </Link>

      <header className="mb-6 mt-4">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={market.category} />
          <span className="micro-label opacity-80">{market.source}</span>
          {settled ? (
            <OutcomeChip outcome={market.outcome ?? 0} />
          ) : days !== null ? (
            <span className="micro-label">· closes {closesLabel(days)}</span>
          ) : null}
        </div>
        <h1 className="mt-3 max-w-3xl text-2xl font-bold leading-snug tracking-tight">
          {market.question}
        </h1>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile
          label="YES price"
          value={market.yes_price !== null ? pct(market.yes_price) : "—"}
          tone="accent"
          sub={market.yes_price === null ? "not yet synced" : "current venue price"}
        />
        <StatTile label="Venue volume" value={compactUsd(market.volume_usd)} sub={market.source} />
        <StatTile
          label={settled ? "Outcome" : "Closes"}
          value={settled ? (market.outcome === 1 ? "YES" : "NO") : closesLabel(days)}
          tone={settled ? (market.outcome === 1 ? "pos" : "neg") : "default"}
          sub={market.close_time ? shortDate(market.close_time) : undefined}
        />
      </div>

      <div className="card mt-4 p-5">
        <div className="micro-label mb-3">YES price — synced venue history</div>
        <ChartArea history={history} />
      </div>

      <div className="card mt-4 p-5">
        <div className="micro-label mb-3">{settled ? "Settlement" : "Trade — virtual ⓥ credits"}</div>
        {settled ? <SettledSummary market={market} /> : <TradeTicket market={market} />}
      </div>

      <p className="micro-label mt-6">{PLAY_MONEY_LINE}</p>
    </div>
  );
}
