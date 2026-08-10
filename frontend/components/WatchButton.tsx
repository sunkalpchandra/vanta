"use client";

import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import { ensureTrader, getTraderKey } from "@/lib/trader";
import { getWatchedIds, toggleWatch } from "@/lib/watch";

/**
 * Star toggle that watches a market for 24h price moves. Presentational — the
 * parent decides where it sits (a market row or the detail header) and whether
 * it starts filled (`initialWatched`). Server-truth via lib/watch; the trading
 * key is the identity, so it reuses lib/trader.
 *
 * In the static demo there is no backend, so the control is disabled and says
 * so rather than pretending to persist anything.
 */
export function WatchButton({
  eventId,
  initialWatched = false,
  onChange,
}: {
  eventId: number;
  initialWatched?: boolean;
  onChange?: (watched: boolean) => void;
}) {
  const [watched, setWatched] = useState(initialWatched);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // Reflect the real server-side watch state: if a trader key exists, fetch
  // whether this market is already watched so the star isn't stuck unfilled.
  useEffect(() => {
    if (IS_STATIC || initialWatched || !getTraderKey()) return;
    let cancelled = false;
    getWatchedIds()
      .then((ids) => !cancelled && ids.includes(eventId) && setWatched(true))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [eventId, initialWatched]);

  if (IS_STATIC) {
    return (
      <button
        type="button"
        disabled
        aria-label="Watchlist unavailable in the static demo"
        title="Watchlists need the live backend — run it to watch this market."
        className="shrink-0 cursor-not-allowed rounded px-1 text-base leading-none text-muted opacity-50"
      >
        ☆
      </button>
    );
  }

  async function toggle(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      // Reuse the stored trading identity; ensureTrader() with no email returns
      // the existing key and throws only when none has been created yet.
      await ensureTrader();
    } catch {
      setNote("Start trading to build a watchlist.");
      setBusy(false);
      return;
    }
    const next = !watched;
    try {
      if (!(await toggleWatch(eventId, next))) throw new Error("rejected");
      setWatched(next);
      onChange?.(next);
    } catch {
      setNote("Couldn’t update your watchlist — is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={watched}
        aria-label={watched ? "Stop watching this market" : "Watch this market"}
        title={watched ? "Watching — click to stop" : "Watch for 24h price moves"}
        className={`shrink-0 rounded px-1 text-base leading-none transition-colors disabled:opacity-50 ${
          watched ? "text-accent" : "text-muted hover:text-ink-2"
        }`}
      >
        {watched ? "★" : "☆"}
      </button>
      {note && <span className="text-xs text-neg">{note}</span>}
    </span>
  );
}
