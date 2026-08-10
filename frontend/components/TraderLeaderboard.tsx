import type { TraderBoard } from "@/lib/types";
import { fmtSignedCredits } from "@/lib/trader";

/** Play-money trader standings, ranked by lifetime P&L against the ⓥ10,000
 * everyone starts with. Server component — reads the baked board in static
 * mode, the live endpoint otherwise. */
export function TraderLeaderboard({ board }: { board: TraderBoard | null }) {
  const traders = board?.traders ?? [];
  if (traders.length === 0) {
    return (
      <div className="card p-6 text-sm text-muted">
        No traders yet — be the first to open a position on the{" "}
        <a href="markets/" className="text-accent hover:underline">
          markets
        </a>{" "}
        page.
      </div>
    );
  }
  return (
    <div className="card divide-y divide-line/60">
      {traders.map((t, i) => {
        const up = t.lifetime_pnl >= 0;
        return (
          <div key={t.user_id} className="flex items-center gap-4 px-5 py-3">
            <span className="num w-6 text-right text-sm text-muted">{i + 1}</span>
            <span className="flex-1 truncate text-sm text-ink">{t.name}</span>
            <span className="num hidden text-xs text-muted sm:block">{t.n_trades} trades</span>
            <span className="num w-24 text-right text-sm text-ink-2">
              ⓥ{t.equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
            <span className={`num w-24 text-right text-sm font-bold ${up ? "text-pos" : "text-neg"}`}>
              {fmtSignedCredits(t.lifetime_pnl)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
