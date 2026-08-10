import { getAgentLeaderboard } from "@/lib/data";

export const metadata = { title: "agent leaderboard — vanta" };

const AGENT_LABELS: Record<string, string> = {
  research: "Research Agent",
  quant: "Quant Agent",
  market: "Market Agent",
  sentiment: "Sentiment Agent",
  historian: "Historian Agent",
  synthesis: "Synthesis Agent",
};

export default async function AgentsPage() {
  const rows = await getAgentLeaderboard();
  const maxBrier = Math.max(0.25, ...rows.map((r) => r.brier));
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Agent Leaderboard</h1>
        <p className="mt-1 text-sm text-ink-2">
          The internal forecaster competition: every agent&apos;s call is frozen at resolution and
          scored against reality. Lower Brier is better; the synthesis pool should beat its inputs.
        </p>
      </div>
      {rows.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No live-resolved questions yet — resolve questions to start the competition.
        </div>
      ) : (
        <div className="card divide-y divide-line/60">
          {rows.map((row, i) => (
            <div key={row.agent} className="flex items-center gap-4 px-5 py-4">
              <span className="num w-5 text-right text-sm font-bold text-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className={`text-sm font-semibold ${row.agent === "synthesis" ? "text-accent" : "text-ink"}`}>
                    {AGENT_LABELS[row.agent] ?? row.agent}
                  </span>
                  <span className="num text-xs text-muted">
                    {row.n_resolved} resolved · acc {(row.accuracy * 100).toFixed(0)}% · log{" "}
                    {row.log_score.toFixed(2)}
                  </span>
                </div>
                {/* Brier bar: shorter is better */}
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 rounded-sm bg-surface-2">
                    <div
                      className="h-1.5 rounded-sm bg-accent"
                      style={{ width: `${Math.min(100, (row.brier / maxBrier) * 100)}%` }}
                    />
                  </div>
                  <span className="num w-14 text-right text-xs font-bold text-ink">
                    {row.brier.toFixed(3)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        Only questions resolved through the live pipeline count — the seeded reference corpus
        predates the agents. The skeptic never estimates, so it isn&apos;t scored.
      </p>
    </div>
  );
}
