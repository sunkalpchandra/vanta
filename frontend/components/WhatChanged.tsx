import { getChanges } from "@/lib/data";
import { pct, signedPct } from "@/lib/format";

/** The move between the latest two forecast runs, with the evidence that
 * arrived in between. Hidden when there's nothing to say. */
export async function WhatChanged({ questionId }: { questionId: number }) {
  const changes = await getChanges(String(questionId));
  if (!changes || changes.delta == null || changes.from == null || changes.to == null) return null;
  if (Math.abs(changes.delta) < 0.005 && changes.new_evidence.length === 0) return null;
  return (
    <div className="card mt-4 p-5">
      <div className="micro-label mb-2">What changed last run</div>
      <p className="num text-sm text-ink">
        {pct(changes.from)} → {pct(changes.to)}{" "}
        <span className={changes.delta >= 0 ? "text-pos" : "text-neg"}>
          ({signedPct(changes.delta)})
        </span>
      </p>
      {changes.new_evidence.length > 0 && (
        <ul className="mt-2 space-y-1">
          {changes.new_evidence.map((e) => (
            <li key={e.summary} className="text-xs text-ink-2">
              <span className={e.sentiment === "positive" ? "text-pos" : e.sentiment === "negative" ? "text-neg" : "text-muted"}>
                {e.sentiment === "positive" ? "+" : e.sentiment === "negative" ? "−" : "·"}
              </span>{" "}
              {e.summary} <span className="micro-label">({e.source})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
