import Link from "next/link";
import { AlertsStrip } from "@/components/AlertsStrip";
import { MoversStrip } from "@/components/MoversStrip";
import { StatsBar } from "@/components/StatsBar";
import { getAlerts, getMovers, getPredictions, getStats } from "@/lib/data";
import { pct, shortDate } from "@/lib/format";

export const metadata = { title: "digest — vanta" };

export default async function DigestPage() {
  const [movers, alerts, stats, predictions] = await Promise.all([
    getMovers(),
    getAlerts(),
    getStats(),
    getPredictions(),
  ]);
  const recentResolutions = predictions.filter((p) => p.question_id != null).slice(0, 6);
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Digest</h1>
        <p className="mt-1 text-sm text-ink-2">
          The state of the system on one page: what moved, what demands attention, what settled.
        </p>
      </div>
      {stats && <div className="mb-6">{<StatsBar stats={stats} />}</div>}
      <AlertsStrip alerts={alerts} />
      <MoversStrip movers={movers} />
      <section className="mt-2">
        <div className="micro-label mb-3">Recently settled through the live pipeline</div>
        {recentResolutions.length === 0 ? (
          <div className="card p-6 text-sm text-muted">Nothing settled recently.</div>
        ) : (
          <div className="card divide-y divide-line/60">
            {recentResolutions.map((p) => (
              <div key={`${p.question_id}`} className="flex items-center gap-3 px-5 py-3">
                {p.question_id != null ? (
                  <Link
                    href={`/questions/${p.question_id}`}
                    className="min-w-0 flex-1 truncate text-sm text-ink transition-colors hover:text-accent"
                  >
                    {p.question_text}
                  </Link>
                ) : (
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">{p.question_text}</span>
                )}
                <span
                  className={`num shrink-0 rounded px-2 py-0.5 text-[11px] font-bold uppercase ${
                    p.outcome ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
                  }`}
                >
                  {p.outcome ? "yes" : "no"}
                </span>
                <span className="num shrink-0 text-xs text-muted">
                  vanta {pct(p.vanta_probability)} · {shortDate(p.resolved_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
