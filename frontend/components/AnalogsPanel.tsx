import type { AgentReportOut } from "@/lib/types";

interface Analog {
  text: string;
  similarity: number;
  outcome: number;
}

/** The quant agent's historical analogs, pulled from its debate report. */
export function AnalogsPanel({ reports }: { reports: AgentReportOut[] }) {
  const quant = reports.find((r) => r.agent === "quant");
  const analogs = (quant?.details?.analogs as Analog[] | undefined) ?? [];
  if (!analogs.length) return null;
  return (
    <div className="card mt-4 p-5">
      <div className="micro-label mb-3">Historical analogs — quant agent</div>
      <ul className="space-y-2.5">
        {analogs.map((a) => (
          <li key={a.text} className="flex items-center gap-3">
            <span
              className={`num w-8 shrink-0 text-center text-[11px] font-bold uppercase ${
                a.outcome ? "text-pos" : "text-neg"
              }`}
            >
              {a.outcome ? "yes" : "no"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-ink-2" title={a.text}>
                {a.text}
              </p>
              <div className="mt-1 h-1 rounded-sm bg-surface-2">
                <div
                  className="h-1 rounded-sm bg-accent/70"
                  style={{ width: `${Math.round(a.similarity * 100)}%` }}
                />
              </div>
            </div>
            <span className="num w-10 shrink-0 text-right text-xs text-muted">
              {(a.similarity * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
