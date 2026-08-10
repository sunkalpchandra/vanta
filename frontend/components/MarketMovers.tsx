"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { pct } from "@/lib/format";
import { IS_STATIC } from "@/lib/config";
import {
  formatMoverDelta,
  getMovers,
  moverTone,
  type MarketMover,
} from "@/lib/marketStats";

type MoversState = "loading" | "ready" | "empty" | "error";

const DISCLAIMER = "play money · paper trading · real market prices";

const TONE_CLASS: Record<"pos" | "neg" | "flat", string> = {
  pos: "text-pos",
  neg: "text-neg",
  flat: "text-muted",
};

/**
 * Biggest YES-price movers over a recent window: a horizontally scrolling strip
 * of markets that moved most, up in the positive tone, down in the negative.
 * Live mode fetches client-side from /api/market-stats/movers; static mode
 * renders the passed-in `movers` prop from the baked snapshot. `windowHours`
 * both drives the live query and labels the strip (defaults to 24, matching the
 * exporter's bake).
 *
 * Play money only — real venue prices, paper trading in ⓥ credits.
 */
export function MarketMovers({
  movers: initial = [],
  windowHours = 24,
  limit = 20,
}: {
  movers?: MarketMover[];
  windowHours?: number;
  limit?: number;
}) {
  const [movers, setMovers] = useState<MarketMover[]>(IS_STATIC ? initial : []);
  const [state, setState] = useState<MoversState>(
    IS_STATIC ? (initial.length ? "ready" : "empty") : "loading",
  );

  useEffect(() => {
    if (IS_STATIC) return;
    let cancelled = false;
    getMovers(windowHours, limit)
      .then((rows) => {
        if (cancelled) return;
        setMovers(rows);
        setState(rows.length ? "ready" : "empty");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [windowHours, limit]);

  return (
    <section className="mb-8" aria-label="Biggest market movers">
      <div className="micro-label mb-3">Biggest movers · last {windowHours}h</div>

      {state === "loading" && (
        <div className="card px-4 py-3 text-sm text-muted">Loading movers…</div>
      )}
      {state === "error" && (
        <div className="card px-4 py-3 text-sm text-muted">
          Couldn&apos;t load movers — is the backend running?
        </div>
      )}
      {state === "empty" && (
        <div className="card px-4 py-3 text-sm text-muted">No market moves in this window yet.</div>
      )}

      {state === "ready" && (
        <div className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none]">
          {movers.map((m) => {
            const tone = moverTone(m.change);
            return (
              <Link
                key={m.event_id}
                href={`/markets/${m.event_id}`}
                className="card card-hover w-60 shrink-0 p-4"
              >
                <div className={`num text-lg font-bold ${TONE_CLASS[tone]}`}>
                  {formatMoverDelta(m.change)}
                </div>
                <div className="num mt-0.5 text-xs text-muted">
                  {pct(m.prev_price)} → {pct(m.yes_price)} · {m.source}
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-snug text-ink-2">{m.question}</p>
              </Link>
            );
          })}
        </div>
      )}

      <p className="micro-label mt-2">{DISCLAIMER}</p>
    </section>
  );
}
