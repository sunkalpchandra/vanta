import { TraderStats } from "@/components/TraderStats";
import type { TraderStats as TraderStatsData } from "@/lib/traderStats";
import Link from "next/link";
import { pct, shortDate } from "@/lib/format";
import { fmtCredits, fmtSignedCredits } from "@/lib/trader";
import { pnlColor, type ProfilePosition } from "@/lib/traderProfile";
import type { TradeRecord } from "@/lib/trader";

/** Normalized view model for a trader page. Live mode fills everything; static
 * mode renders a lightweight header from the baked leaderboard row, leaving the
 * live-only fields null and positions/trades empty. */
export interface TraderProfileView {
  name: string;
  joined: string | null;
  balance: number | null; // null in static mode (not baked)
  equity: number;
  lifetimePnl: number; // equity − ⓥ10,000
  realizedPnl: number | null; // null in static mode
  nTrades: number;
  positions: ProfilePosition[];
  recentTrades: TradeRecord[];
  stats?: TraderStatsData | null;
  isStatic: boolean;
}

/** Whole shares print bare; fractional lots keep at most 2 decimals. */
const fmtShares = (n: number): string =>
  Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);

const creditsOrDash = (n: number | null): string => (n === null ? "—" : fmtCredits(n));

/** Public trader profile: colored header stats, positions marked to venue
 * prices, and a recent-trade log. Server component (no client state). */
export function TraderProfile({ view }: { view: TraderProfileView }) {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <div className="micro-label">trader</div>
        <h1 className="mt-1 break-all text-2xl font-bold tracking-tight">{view.name}</h1>
        <p className="mt-1 text-sm text-ink-2">
          Play-money book, marked to the latest synced venue prices — play money · paper
          trading · real market prices.
        </p>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="card p-5">
          <div className="micro-label">Equity</div>
          <div className="num mt-1 text-xl font-bold text-ink">{fmtCredits(view.equity)}</div>
          <div className="mt-1 text-xs text-muted">
            balance {creditsOrDash(view.balance)}
          </div>
        </div>
        <div className="card p-5">
          <div className="micro-label">Lifetime P&amp;L</div>
          <div className={`num mt-1 text-xl font-bold ${pnlColor(view.lifetimePnl)}`}>
            {fmtSignedCredits(view.lifetimePnl)}
          </div>
          <div className="mt-1 text-xs text-muted">vs ⓥ10,000 start</div>
        </div>
        <div className="card p-5">
          <div className="micro-label">Trades</div>
          <div className="num mt-1 text-xl font-bold text-ink">{view.nTrades}</div>
          <div className="mt-1 text-xs text-muted">
            {view.joined ? `joined ${shortDate(view.joined)}` : " "}
          </div>
        </div>
      </div>

      {view.isStatic ? (
        <div className="card mb-8 p-4 text-sm text-muted">
          Snapshot view — full position and trade detail needs the live backend.
        </div>
      ) : (
        <>
          <div className="micro-label mb-3">Positions</div>
          {view.stats && (
            <div className="mb-8">
              <TraderStats stats={view.stats} />
            </div>
          )}
          {view.positions.length === 0 ? (
            <div className="card mb-8 p-8 text-center text-sm text-muted">No positions yet.</div>
          ) : (
            <div className="card mb-8 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="micro-label px-5 py-3 font-normal">Market</th>
                    <th className="micro-label px-5 py-3 text-center font-normal">Side</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Shares</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Avg</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Mark</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Unreal. P&amp;L</th>
                  </tr>
                </thead>
                <tbody>
                  {view.positions.map((p) => {
                    const closed = p.settled || p.shares <= 0;
                    return (
                      <tr
                        key={`${p.event_id}-${p.side}`}
                        className="border-b border-line/60 last:border-0"
                      >
                        <td className="max-w-xs px-5 py-3">
                          <Link
                            href={`/markets/${p.event_id}`}
                            className="text-ink transition-colors hover:text-accent"
                          >
                            {p.question}
                          </Link>
                          {closed && (
                            <span className="ml-2 text-[11px] uppercase tracking-wider text-muted">
                              {p.settled ? "settled" : "closed"}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 text-center">
                          <span className="num text-xs uppercase tracking-wider text-ink-2">
                            {p.side}
                          </span>
                        </td>
                        <td className="num px-5 py-3 text-right text-ink-2">
                          {fmtShares(p.shares)}
                        </td>
                        <td className="num px-5 py-3 text-right text-ink-2">{pct(p.avg_price)}</td>
                        <td className="num px-5 py-3 text-right text-ink-2">
                          {p.current_price === null ? "—" : pct(p.current_price)}
                        </td>
                        <td
                          className={`num px-5 py-3 text-right ${
                            p.unrealized_pnl === null ? "text-muted" : pnlColor(p.unrealized_pnl)
                          }`}
                        >
                          {p.unrealized_pnl === null ? "—" : fmtSignedCredits(p.unrealized_pnl)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="micro-label mb-3">Recent trades</div>
          {view.recentTrades.length === 0 ? (
            <div className="card p-8 text-center text-sm text-muted">No trades yet.</div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="micro-label px-5 py-3 font-normal">Market</th>
                    <th className="micro-label px-5 py-3 text-center font-normal">Action</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Shares</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">Price</th>
                    <th className="micro-label px-5 py-3 text-right font-normal">When</th>
                  </tr>
                </thead>
                <tbody>
                  {view.recentTrades.map((t) => (
                    <tr key={t.id} className="border-b border-line/60 last:border-0">
                      <td className="max-w-xs px-5 py-3">
                        <Link
                          href={`/markets/${t.event_id}`}
                          className="text-ink transition-colors hover:text-accent"
                        >
                          {t.question ?? `Market #${t.event_id}`}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-center">
                        <span
                          className={`num text-xs font-bold uppercase tracking-wider ${
                            t.action === "buy" ? "text-pos" : "text-neg"
                          }`}
                        >
                          {t.action} {t.side}
                        </span>
                      </td>
                      <td className="num px-5 py-3 text-right text-ink-2">{fmtShares(t.shares)}</td>
                      <td className="num px-5 py-3 text-right text-ink-2">{pct(t.price)}</td>
                      <td className="num px-5 py-3 text-right text-muted">
                        {shortDate(t.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div className="mt-8">
        <Link href="/portfolio" className="text-sm text-accent hover:underline">
          ← Trader leaderboard
        </Link>
      </div>
    </div>
  );
}
