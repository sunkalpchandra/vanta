import { describeStrategy, type AgentTraderRow } from "@/lib/agentTraders";
import { fmtCredits, fmtSignedCredits } from "@/lib/trader";

/** Presentational agent-trader dashboard: one card per bot with its strategy
 * blurb, equity, lifetime P&L (colored), and activity. No fetch, no client
 * state — the page passes the rows it loaded (live endpoint or baked snapshot).
 * Play money · paper trading · real market prices. */
export function AgentTraderBoard({ rows }: { rows: AgentTraderRow[] }) {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Agent Traders</h1>
        <p className="mt-1 text-sm text-ink-2">
          vanta trades its own forecasts in play money. Each bot puts ⓥ credits behind one
          deterministic rule over the pipeline&apos;s numbers — near-zero edge means the bots mostly
          track the market, which is the honest outcome.
        </p>
        <p className="micro-label mt-2">play money · paper trading · real market prices</p>
      </div>

      {rows.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No agent-traders yet — the bots appear here once they have been created and start trading
          the live markets.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((r) => {
            const up = r.lifetime_pnl >= 0;
            return (
              <div key={r.name} className="card px-5 py-4">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="num text-sm font-semibold text-ink">{r.name}</span>
                  <span className="micro-label">{r.strategy}</span>
                </div>
                <p className="mt-2 text-xs text-ink-2">{describeStrategy(r.strategy)}</p>

                <div className="mt-4 flex items-end justify-between gap-3">
                  <div>
                    <div className="micro-label">Equity</div>
                    <div className="num mt-1 text-xl font-bold text-ink">{fmtCredits(r.equity)}</div>
                  </div>
                  <div className="text-right">
                    <div className="micro-label">Lifetime P&amp;L</div>
                    <div className={`num mt-1 text-xl font-bold ${up ? "text-pos" : "text-neg"}`}>
                      {fmtSignedCredits(r.lifetime_pnl)}
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line/60 pt-3 text-xs text-muted">
                  <span className="num">
                    {r.n_trades} trade{r.n_trades === 1 ? "" : "s"}
                  </span>
                  <span aria-hidden>·</span>
                  <span className="num">{r.n_positions} open</span>
                  <span aria-hidden>·</span>
                  <span className="num">{fmtCredits(r.balance)} cash</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-muted">
        Bots trade through the exact same play-money engine as human traders, sized as a small
        fraction of their ⓥ10,000 starting bankroll. Numbers only — no language model ever touches a
        trade.
      </p>
    </div>
  );
}
