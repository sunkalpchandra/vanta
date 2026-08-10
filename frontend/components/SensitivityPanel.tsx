import { IS_STATIC } from "@/lib/config";
import { getSensitivity } from "@/lib/data";
import { signedPct } from "@/lib/format";

/** Which signals actually move this forecast — leave-one-out deltas from the
 * real pipeline. Server component; data comes from the API or the snapshot. */
export async function SensitivityPanel({ questionId }: { questionId: number }) {
  const { items } = await getSensitivity(String(questionId));
  if (!items.length) return null;
  const maxAbs = Math.max(...items.map((i) => Math.abs(i.delta)), 0.001);
  return (
    <div className="card mt-4 p-5">
      <div className="micro-label mb-1">Evidence sensitivity</div>
      <p className="mb-3 text-xs text-muted">
        How much the forecast would move if each signal were removed — leave-one-out over the real
        pipeline{IS_STATIC ? " (baked at snapshot time)" : ""}.
      </p>
      <ul className="space-y-2.5">
        {items.map((item) => (
          <li key={item.summary} className="flex items-center gap-3">
            <span
              className={`num w-14 shrink-0 text-right text-xs font-bold ${
                item.delta > 0 ? "text-pos" : item.delta < 0 ? "text-neg" : "text-muted"
              }`}
            >
              {signedPct(item.delta)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-ink-2" title={item.summary}>
                {item.summary}
              </p>
              <div className="mt-1 h-1 rounded-sm bg-surface-2">
                <div
                  className={`h-1 rounded-sm ${item.delta >= 0 ? "bg-pos/70" : "bg-neg/70"}`}
                  style={{ width: `${Math.round((Math.abs(item.delta) / maxAbs) * 100)}%` }}
                />
              </div>
            </div>
            <span className="micro-label w-20 shrink-0 truncate text-right">{item.source}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
