"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { IS_STATIC } from "@/lib/config";
import { formatTapeLine, getActivity, type TradeTapeItem } from "@/lib/activity";

type TapeState = "loading" | "ready" | "empty" | "error";

const DISCLAIMER = "play money · paper trading · real market prices";

/**
 * Public activity tape: a compact, horizontally scrolling strip of the most
 * recent play-money trades across all traders. Live mode fetches client-side
 * from the API; static mode renders the passed-in `sample` array (honestly
 * labeled a sample, since the static export has no live backend). Buys read in
 * the positive tone, sells muted. Presentational only — page placement is
 * wired separately.
 */
export function ActivityTape({
  sample = [],
  limit = 30,
}: {
  sample?: TradeTapeItem[];
  limit?: number;
}) {
  const reduceMotion = useReducedMotion();
  const [items, setItems] = useState<TradeTapeItem[]>(IS_STATIC ? sample : []);
  const [state, setState] = useState<TapeState>(
    IS_STATIC ? (sample.length ? "ready" : "empty") : "loading",
  );

  useEffect(() => {
    if (IS_STATIC) return;
    let cancelled = false;
    getActivity(limit)
      .then((trades) => {
        if (cancelled) return;
        setItems(trades);
        setState(trades.length ? "ready" : "empty");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [limit]);

  return (
    <section aria-label="Recent trades" className="mb-8">
      <div className="micro-label mb-3 flex items-center gap-2">
        <span aria-hidden className={IS_STATIC ? "text-muted" : "text-pos"}>
          ●
        </span>
        <span>{IS_STATIC ? "activity tape · sample" : "activity tape · live"}</span>
      </div>

      {state === "loading" && (
        <div className="card px-4 py-3 text-sm text-muted">Loading recent trades…</div>
      )}
      {state === "error" && (
        <div className="card px-4 py-3 text-sm text-muted">
          Couldn&apos;t load the tape — is the backend running?
        </div>
      )}
      {state === "empty" && <div className="card px-4 py-3 text-sm text-muted">No trades yet.</div>}

      {state === "ready" && (
        <ul className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" role="list">
          {items.map((t, i) => (
            <motion.li
              key={t.id}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: Math.min(i * 0.03, 0.3) }}
              className="card shrink-0 px-3 py-2"
            >
              <span
                title={formatTapeLine(t, 200)}
                className={`num block max-w-xs truncate text-xs ${
                  t.action === "buy" ? "text-pos" : "text-muted"
                }`}
              >
                {formatTapeLine(t)}
              </span>
            </motion.li>
          ))}
        </ul>
      )}

      <p className="micro-label mt-2">{DISCLAIMER}</p>
    </section>
  );
}
