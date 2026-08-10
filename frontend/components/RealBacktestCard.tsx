import type { RealBacktestOut } from "@/lib/types";
import { pct } from "@/lib/format";

function Metric({ label, vanta, market }: { label: string; vanta: string; market: string }) {
  return (
    <div>
      <div className="micro-label">{label}</div>
      <div className="num mt-1 text-lg font-bold text-accent">{vanta}</div>
      <div className="num text-xs text-muted">market {market}</div>
    </div>
  );
}

/** The only accuracy numbers that mean anything: the pipeline scored against
 * real resolved markets, on information available before resolution. */
export function RealBacktestCard({ result }: { result: RealBacktestOut | null }) {
  if (!result || result.available === false || !result.n) {
    return (
      <div className="card p-6 text-sm text-muted">
        Real-market backtest not yet baked into this snapshot — run the ingest and
        backtest against a live backend (see docs/BACKTEST.md).
      </div>
    );
  }
  const src = Object.entries(result.sources)
    .map(([k, v]) => `${k} ${v.toLocaleString("en-US")}`)
    .join(" · ");
  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="micro-label">
          {result.n.toLocaleString("en-US")} resolved markets · T−{result.horizon_days}d snapshot ·{" "}
          {src}
        </span>
        <span className="micro-label ml-auto">
          coverage {pct(result.coverage)} of resolved corpus
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric
          label="Brier (lower better)"
          vanta={result.vanta_brier?.toFixed(4) ?? "—"}
          market={result.market_brier?.toFixed(4) ?? "—"}
        />
        <Metric
          label="Log score (lower better)"
          vanta={result.vanta_log?.toFixed(4) ?? "—"}
          market={result.market_log?.toFixed(4) ?? "—"}
        />
        <Metric
          label="Directional accuracy"
          vanta={result.vanta_accuracy != null ? pct(result.vanta_accuracy) : "—"}
          market={result.market_accuracy != null ? pct(result.market_accuracy) : "—"}
        />
        <div>
          <div className="micro-label">No-skill benchmark</div>
          <div className="num mt-1 text-lg font-bold text-ink-2">
            {result.base_rate_brier?.toFixed(4) ?? "—"}
          </div>
          <div className="num text-xs text-muted">
            always-predict-{result.outcome_base_rate != null ? pct(result.outcome_base_rate) : "—"}
          </div>
        </div>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-muted">
        Leakage-free: for each market the pipeline saw only the venue price {result.horizon_days}{" "}
        days before close plus category base rates learned from <em>other</em> events; the market
        is scored on the identical snapshot. Expect vanta ≈ market — beating deep prediction
        markets is hard, and this scorecard reports whatever the data says.
      </p>
    </div>
  );
}
