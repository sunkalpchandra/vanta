"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { shortDate } from "@/lib/format";
import { authHeaders, clearTraderKey, fmtCredits, fmtSignedCredits, getTraderKey, round2 } from "@/lib/trader";
import { getTradeHistory, summarize, type TradeRow } from "@/lib/tradeHistory";
import { StatTile } from "./StatTile";

type ViewState = "loading" | "nokey" | "rejected" | "error" | "ready";

/** The caller's full play-money execution log, with CSV downloads of trades
 * and positions. A plain `<a download>` can't carry the X-API-Key header the
 * CSV endpoints require, so downloads fetch with authHeaders() and stream the
 * response through a Blob. */
export function TradeHistory() {
  const [state, setState] = useState<ViewState>("loading");
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [dlError, setDlError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (getTraderKey() === null) {
      setState("nokey");
      return;
    }
    setState("loading");
    try {
      setTrades(await getTradeHistory());
      setState("ready");
    } catch (err) {
      // A rejected key surfaces as a 401 inside the thrown message.
      setState(err instanceof Error && err.message.includes("401") ? "rejected" : "error");
    }
  }, []);

  useEffect(() => {
    if (!IS_STATIC) load();
  }, [load]);

  const download = useCallback(async (path: string, filename: string) => {
    setDlError(null);
    try {
      const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setDlError("Download failed — is the backend running?");
    }
  }, []);

  if (IS_STATIC) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        The static demo has no trading backend, so there is no trade history to show. Connect the
        backend locally to trade with ⓥ10,000 play credits and export your book as CSV.
        <div className="micro-label mt-3">play money · paper trading · real market prices</div>
      </div>
    );
  }

  if (state === "loading") {
    return <div className="card p-8 text-center text-sm text-muted">Loading trade history…</div>;
  }

  if (state === "nokey") {
    return (
      <div className="card p-8 text-center">
        <div className="micro-label">no trader identity yet</div>
        <p className="mt-2 text-sm text-ink-2">
          Start trading with ⓥ10,000 play credits — open any market and the trade ticket sets you
          up in one click. Your executions show up here.
        </p>
        <Link
          href="/markets"
          className="mt-4 inline-block rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          Start trading
        </Link>
        <div className="micro-label mt-4">play money · paper trading · real market prices</div>
      </div>
    );
  }

  if (state === "rejected") {
    return (
      <div className="card p-8 text-center text-sm text-ink-2">
        The trading key stored in this browser was rejected by the backend.
        <div className="mt-3">
          <button
            onClick={() => {
              clearTraderKey();
              setState("nokey");
            }}
            className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
          >
            Forget key &amp; start over
          </button>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        Couldn&apos;t load your trade history — is the backend running?
      </div>
    );
  }

  const summary = summarize(trades);

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-4">
        <StatTile label="executions" value={String(summary.n)} sub="total trades placed" />
        <StatTile label="volume" value={fmtCredits(summary.volume)} sub="ⓥ notional traded" />
        <StatTile label="buys" value={String(summary.buys)} tone="pos" sub="opened / added" />
        <StatTile label="sells" value={String(summary.sells)} tone="neg" sub="closed / reduced" />
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          onClick={() => download("/api/export/trades.csv", "vanta-trades.csv")}
          className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
        >
          Download trades CSV
        </button>
        <button
          onClick={() => download("/api/export/positions.csv", "vanta-positions.csv")}
          className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
        >
          Download positions CSV
        </button>
        {dlError && <span className="text-xs text-neg">{dlError}</span>}
      </div>

      <div className="card mt-6 overflow-x-auto">
        <div className="micro-label px-5 pt-4">executions — newest first</div>
        {trades.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted">
            No trades yet — buy YES or NO on the{" "}
            <Link href="/markets" className="text-accent hover:underline">
              Markets
            </Link>{" "}
            page.
          </p>
        ) : (
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="micro-label px-5 py-3 font-normal">When</th>
                <th className="micro-label px-5 py-3 font-normal">Action</th>
                <th className="micro-label px-5 py-3 font-normal">Side</th>
                <th className="micro-label px-5 py-3 font-normal">Market</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Shares @ price</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Cost</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} className="border-b border-line/60 last:border-0">
                  <td className="num px-5 py-3 text-xs text-muted">{shortDate(t.created_at)}</td>
                  <td className="px-5 py-3 font-semibold uppercase text-ink-2">{t.action}</td>
                  <td className="px-5 py-3">
                    <SideChip side={t.side} />
                  </td>
                  <td className="max-w-96 truncate px-5 py-3 text-ink">{t.question ?? `#${t.event_id}`}</td>
                  <td className="num px-5 py-3 text-right text-ink-2">
                    {t.shares} @ {t.price.toFixed(2)}
                  </td>
                  <td className={`num px-5 py-3 text-right font-bold ${t.cost >= 0 ? "text-pos" : "text-neg"}`}>
                    {fmtSignedCredits(round2(t.cost))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="micro-label mt-6">play money · paper trading · real market prices</p>
    </div>
  );
}

function SideChip({ side }: { side: "yes" | "no" }) {
  return (
    <span
      className={`num rounded px-2 py-0.5 text-xs font-bold ${
        side === "yes" ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
      }`}
    >
      {side.toUpperCase()}
    </span>
  );
}
