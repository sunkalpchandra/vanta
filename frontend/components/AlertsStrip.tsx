import Link from "next/link";
import type { AlertItem } from "@/lib/types";
import { signedPct } from "@/lib/format";

export function AlertsStrip({ alerts }: { alerts: AlertItem[] }) {
  if (!alerts.length) return null;
  return (
    <section className="mb-6" aria-label="Alerts">
      <div className="card flex flex-wrap items-center gap-x-5 gap-y-2 border-accent/25 px-5 py-3">
        <span className="micro-label !text-accent">◆ alerts</span>
        {alerts.slice(0, 3).map((alert) => (
          <Link
            key={`${alert.kind}-${alert.question_id}`}
            href={`/questions/${alert.question_id}`}
            className="group flex min-w-0 items-center gap-2 text-xs"
          >
            <span className={`num font-bold ${alert.value >= 0 ? "text-pos" : "text-neg"}`}>
              {signedPct(alert.value)}
            </span>
            <span className="micro-label shrink-0">{alert.kind}</span>
            <span className="truncate text-ink-2 transition-colors group-hover:text-ink">
              {alert.question}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
