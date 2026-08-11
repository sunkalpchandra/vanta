"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { EquityChart } from "@/components/EquityChart";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { shortDate } from "@/lib/format";
import {
  authHeaders,
  clearTraderKey,
  fmtCredits,
  fmtSignedCredits,
  getTraderKey,
  round2,
  type PortfolioOut,
} from "@/lib/trader";
import { StatTile } from "./StatTile";

type ViewState = "loading" | "nokey" | "rejected" | "error" | "ready";

/** The trader's play-money book: balance, equity, positions marked to the
 * latest synced venue prices, and the recent execution log. */
export function PortfolioView() {
  const [state, setState] = useState<ViewState>("loading");
  const [data, setData] = useState<PortfolioOut | null>(null);
  const [localEquity, setLocalEquity] = useState<{ timestamp: string; cash: number }[]>([]);

  const load = useCallback(async () => {
    if (getTraderKey() === null) {
      setState("nokey");
      return;
    }
    setState("loading");
    try {
      const res = await fetch(`${API_URL}/api/markets/portfolio/me`, { headers: authHeaders() });
      if (res.status === 401) {
        setState("rejected");
        return;
      }
      if (!res.ok) throw new Error(String(res.status));
      setData((await res.json()) as PortfolioOut);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  const loadLocal = useCallback(async () => {
    // Static demo: reconstruct the portfolio from the in-browser engine, marked
    // to the baked market prices (fetched client-side). Fully offline.
    try {
      const [{ localPortfolioSnapshot, loadLocalTrader }, cfg] = await Promise.all([
        import("@/lib/localTrader"),
        import("@/lib/config"),
      ]);
      const res = await fetch(`${cfg.BASE_PATH}/data/markets-sample.json`);
      const sample = res.ok ? await res.json() : { active: [], settled: [] };
      const priceById = new Map<number, number>();
      const outcomeById = new Map<number, number>();
      for (const m of [...(sample.active ?? []), ...(sample.settled ?? [])]) {
        if (m.yes_price != null) priceById.set(m.id, m.yes_price);
        if (m.outcome != null) outcomeById.set(m.id, m.outcome);
      }
      const snap = localPortfolioSnapshot(
        (id) => priceById.get(id) ?? null,
        (id) => outcomeById.get(id) ?? null,
      );
      const allTrades = loadLocalTrader().trades;
      // Cash-flow-from-trades series (matches the backend equity endpoint):
      // start at ⓥ10,000, apply each signed trade cost.
      let cash = 10000;
      const eqPoints = allTrades.length
        ? [{ timestamp: allTrades[0].created_at, cash: 10000 }]
        : [];
      for (const t of allTrades) {
        cash = Math.round((cash + t.cost) * 100) / 100;
        eqPoints.push({ timestamp: t.created_at, cash });
      }
      setLocalEquity(eqPoints);
      const trades = allTrades.slice(-25).reverse();
      setData({
        balance: snap.balance,
        equity: snap.equity,
        realized_pnl_total: snap.realized_pnl_total,
        positions: snap.positions.map((p) => ({
          event_id: p.event_id,
          question: p.question,
          side: p.side,
          shares: p.shares,
          avg_price: p.avg_price,
          realized_pnl: p.realized_pnl,
          settled: p.settled,
          current_price: p.current_price,
          unrealized_pnl: p.unrealized_pnl,
        })),
        recent_trades: trades.map((t) => ({
          id: t.id,
          event_id: t.event_id,
          question: t.question,
          side: t.side,
          action: t.action,
          shares: t.shares,
          price: t.price,
          cost: t.cost,
          created_at: t.created_at,
        })),
      } as PortfolioOut);
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (IS_STATIC) loadLocal();
    else load();
  }, [load, loadLocal]);

  if (state === "loading") {
    return <div className="card p-8 text-center text-sm text-muted">Loading portfolio…</div>;
  }

  if (state === "nokey") {
    return (
      <div className="card p-8 text-center">
        <div className="micro-label">no trader identity yet</div>
        <p className="mt-2 text-sm text-ink-2">
          Start trading with ⓥ10,000 play credits — open any market and the trade ticket sets you
          up in one click.
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

  if (state === "error" || data === null) {
    return (
      <div className="card p-8 text-center text-sm text-muted">
        Couldn&apos;t load the portfolio — is the backend running?
      </div>
    );
  }

  const positions = data.positions ?? [];
  const openPnl = positions.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0);
  const lifetime = round2(data.realized_pnl_total + openPnl);
  const trades = data.recent_trades ?? [];

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="balance" value={fmtCredits(data.balance)} sub="ⓥ play credits on hand" />
        <StatTile
          label="equity"
          value={fmtCredits(data.equity)}
          tone="accent"
          sub="balance + positions at current prices"
        />
        <StatTile
          label="lifetime p&l"
          value={fmtSignedCredits(lifetime)}
          tone={lifetime >= 0 ? "pos" : "neg"}
          sub={`realized ${fmtSignedCredits(round2(data.realized_pnl_total))} · open ${fmtSignedCredits(round2(openPnl))}`}
        />
      </div>
      <div className="card mt-6 overflow-x-auto">
        <div className="micro-label px-5 pt-4">positions</div>
        {positions.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted">
            No positions yet — buy YES or NO on the{" "}
            <Link href="/markets" className="text-accent hover:underline">
              Markets
            </Link>{" "}
            page.
          </p>
        ) : (
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="micro-label px-5 py-3 font-normal">Market</th>
                <th className="micro-label px-5 py-3 font-normal">Side</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Shares</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Avg → now</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Unrealized</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const pnl = p.unrealized_pnl;
                return (
                  <tr key={`${p.event_id}-${p.side}`} className="border-b border-line/60 last:border-0">
                    <td className="max-w-96 px-5 py-3 text-ink">{p.question}</td>
                    <td className="px-5 py-3">
                      <SideChip side={p.side} />
                      {p.settled && <span className="micro-label ml-2">settled</span>}
                    </td>
                    <td className="num px-5 py-3 text-right text-ink-2">{p.shares}</td>
                    <td className="num px-5 py-3 text-right text-ink-2">
                      {p.avg_price.toFixed(2)} →{" "}
                      {p.current_price !== null ? p.current_price.toFixed(2) : "—"}
                    </td>
                    <td
                      className={`num px-5 py-3 text-right font-bold ${
                        pnl === null ? "text-muted" : pnl >= 0 ? "text-pos" : "text-neg"
                      }`}
                    >
                      {pnl === null ? "—" : fmtSignedCredits(round2(pnl))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <div className="card mt-4">
        <div className="micro-label px-5 pt-4">recent trades</div>
        {trades.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted">No trades yet.</p>
        ) : (
          <ul className="divide-y divide-line/60">
            {trades.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3 text-sm">
                <span className="num text-xs text-muted">{shortDate(t.created_at)}</span>
                <span className="font-semibold uppercase text-ink-2">{t.action}</span>
                <SideChip side={t.side} />
                <span className="num text-ink-2">
                  {t.shares} @ {t.price.toFixed(2)}
                </span>
                {t.question && <span className="min-w-0 flex-1 truncate text-ink">{t.question}</span>}
                <span
                  className={`num ml-auto font-bold ${t.cost >= 0 ? "text-pos" : "text-neg"}`}
                >
                  {fmtSignedCredits(round2(t.cost))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <section className="mt-8">
        <div className="micro-label mb-3">Cash flow from trades</div>
        <EquityChart points={IS_STATIC ? localEquity : undefined} />
      </section>
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
