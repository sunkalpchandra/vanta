import { fmtCredits, fmtSignedCredits } from "@/lib/trader";
import { formatWinRate, pnlTone, type TraderStats as TraderStatsData } from "@/lib/traderStats";

/** pnlTone bucket -> Tailwind text color (flat book reads as neutral ink). */
const TONE_CLASS: Record<ReturnType<typeof pnlTone>, string> = {
  pos: "text-pos",
  neg: "text-neg",
  flat: "text-ink",
};

/** One highlighted market (best / worst settled result). */
function HighlightTile({ label, trade }: { label: string; trade: TraderStatsData["best_trade"] }) {
  if (!trade) return null;
  return (
    <div className="card px-5 py-4">
      <div className="micro-label">{label}</div>
      <div className="mt-1.5 line-clamp-2 text-sm text-ink">{trade.question}</div>
      <div className={`num mt-1 text-sm font-bold ${TONE_CLASS[pnlTone(trade.realized_pnl)]}`}>
        {fmtSignedCredits(trade.realized_pnl)}
      </div>
    </div>
  );
}

/** Presentational trader statistics: win rate, W–L record, net realized P&L,
 * activity, and the trader's best / worst settled markets. Static tiles — the
 * profile page passes the stats the endpoint embedded (no fetch, no client
 * state). Play money · paper trading · real market prices. */
export function TraderStats({ stats }: { stats: TraderStatsData }) {
  return (
    <section className="mb-8">
      <div className="micro-label mb-3">Statistics</div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card px-5 py-4">
          <div className="micro-label">Win rate</div>
          <div className="num mt-1.5 text-2xl font-bold text-ink">{formatWinRate(stats.win_rate)}</div>
          <div className="mt-1 text-xs text-muted">
            {stats.n_settled} settled position{stats.n_settled === 1 ? "" : "s"}
          </div>
        </div>

        <div className="card px-5 py-4">
          <div className="micro-label">Record</div>
          <div className="num mt-1.5 text-2xl font-bold text-ink">
            <span className="text-pos">{stats.n_wins}W</span>
            <span className="mx-1 text-muted">·</span>
            <span className="text-neg">{stats.n_losses}L</span>
          </div>
          <div className="mt-1 text-xs text-muted">wins · losses</div>
        </div>

        <div className="card px-5 py-4">
          <div className="micro-label">Realized P&amp;L</div>
          <div className={`num mt-1.5 text-2xl font-bold ${TONE_CLASS[pnlTone(stats.total_realized)]}`}>
            {fmtSignedCredits(stats.total_realized)}
          </div>
          <div className="mt-1 text-xs text-muted">across settled</div>
        </div>

        <div className="card px-5 py-4">
          <div className="micro-label">Trades</div>
          <div className="num mt-1.5 text-2xl font-bold text-ink">{stats.n_trades}</div>
          <div className="mt-1 text-xs text-muted">
            {stats.n_markets} market{stats.n_markets === 1 ? "" : "s"} · avg {fmtCredits(stats.avg_trade_size)}
          </div>
        </div>
      </div>

      {(stats.best_trade || stats.worst_trade) && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <HighlightTile label="Best market" trade={stats.best_trade} />
          <HighlightTile label="Worst market" trade={stats.worst_trade} />
        </div>
      )}
    </section>
  );
}
