import type { EvidenceOut } from "@/lib/types";
import { shortDate } from "@/lib/format";

export function EvidenceList({ evidence }: { evidence: EvidenceOut[] }) {
  if (!evidence.length) {
    return <p className="text-sm text-muted">No ingested evidence for this question yet.</p>;
  }
  const sorted = [...evidence].sort((a, b) => b.impact - a.impact);
  return (
    <ul className="space-y-2">
      {sorted.map((e, i) => (
        <li key={i} className="card flex items-start gap-3 p-3">
          <span
            className={`num mt-0.5 w-5 shrink-0 text-center text-sm font-bold ${
              e.sentiment === "positive"
                ? "text-pos"
                : e.sentiment === "negative"
                  ? "text-neg"
                  : "text-muted"
            }`}
            aria-label={e.sentiment}
          >
            {e.sentiment === "positive" ? "+" : e.sentiment === "negative" ? "−" : "·"}
          </span>
          <div className="min-w-0">
            <p className="text-sm text-ink-2">{e.summary}</p>
            <p className="micro-label mt-1">
              {e.source} · impact {e.impact.toFixed(1)} · {shortDate(e.created_at)}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
