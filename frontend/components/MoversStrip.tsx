import Link from "next/link";
import type { MoverCard } from "@/lib/types";
import { pct, signedPct } from "@/lib/format";

export function MoversStrip({ movers }: { movers: MoverCard[] }) {
  if (!movers.length) return null;
  return (
    <section className="mb-8" aria-label="Biggest probability moves">
      <div className="micro-label mb-3">
        Biggest moves · last {movers[0].window_days}d
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none]">
        {movers.map((m) => (
          <Link
            key={m.question_id}
            href={`/questions/${m.question_id}`}
            className="card card-hover w-60 shrink-0 p-4"
          >
            <div className={`num text-lg font-bold ${m.delta >= 0 ? "text-pos" : "text-neg"}`}>
              {m.delta >= 0 ? "▲" : "▼"} {signedPct(m.delta)}
            </div>
            <div className="num mt-0.5 text-xs text-muted">
              {pct(m.previous)} → {pct(m.current)}
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-snug text-ink-2">{m.question}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
