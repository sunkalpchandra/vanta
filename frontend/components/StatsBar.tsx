import type { StatsOut } from "@/lib/types";
import { StatTile } from "./StatTile";

export function StatsBar({ stats }: { stats: StatsOut }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile
        label="Resolved questions"
        value={String(stats.n_resolved)}
        sub={`${stats.n_live_questions} live · view archive`}
        href="/archive"
      />
      <StatTile
        label="vanta accuracy"
        value={stats.vanta_accuracy != null ? `${Math.round(stats.vanta_accuracy * 100)}%` : "—"}
        tone="accent"
        sub={
          stats.market_accuracy != null
            ? `market ${Math.round(stats.market_accuracy * 100)}%`
            : undefined
        }
      />
      <StatTile
        label="vanta Brier"
        value={stats.vanta_brier != null ? stats.vanta_brier.toFixed(3) : "—"}
        sub={
          stats.market_brier != null
            ? `market ${stats.market_brier.toFixed(3)} · log ${stats.vanta_log_score?.toFixed(2) ?? "—"} vs ${
                stats.market_log_score?.toFixed(2) ?? "—"
              }`
            : undefined
        }
      />
      <StatTile
        label="Avg live edge"
        value={stats.avg_abs_edge != null ? `±${Math.round(stats.avg_abs_edge * 100)}%` : "—"}
        sub="mean |vanta − market|"
      />
    </div>
  );
}
