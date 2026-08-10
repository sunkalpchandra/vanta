import Link from "next/link";
import { CopyBriefButton } from "@/components/CopyBriefButton";
import { TodayDate } from "@/components/TodayDate";
import { getBrief } from "@/lib/data";
import { pct, signedPct } from "@/lib/format";

export default async function BriefPage() {
  const brief = await getBrief();
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <TodayDate />
          <h1 className="mt-2 text-2xl font-bold tracking-tight">vanta Morning Brief</h1>
          <p className="mt-1 text-sm text-ink-2">
            {brief.length > 0
              ? `${brief.length} things the world is most wrong about today.`
              : "The things the world is most wrong about today."}
          </p>
        </div>
        <CopyBriefButton brief={brief} />
      </div>
      {brief.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          The brief is generated from live forecasts — start the backend to see it.
        </div>
      ) : (
        <ol className="space-y-4">
          {brief.map((item) => (
            <li key={item.question_id}>
              <Link
                href={`/questions/${item.question_id}`}
                className="card card-hover flex gap-5 p-5"
              >
                <span className="num text-3xl font-bold text-muted">{item.rank}</span>
                <div className="min-w-0 flex-1">
                  <h3 className="text-[15px] font-semibold leading-snug text-ink">{item.question}</h3>
                  <p className="mt-1.5 text-sm text-ink-2">{item.one_liner}</p>
                  <div className="num mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
                    <span className="text-ink-2">
                      market <strong className="text-ink">{pct(item.market_probability)}</strong>
                    </span>
                    <span className="text-ink-2">
                      vanta <strong className="text-accent">{pct(item.vanta_probability)}</strong>
                    </span>
                    <span className={`font-bold ${item.edge >= 0 ? "text-pos" : "text-neg"}`}>
                      {signedPct(item.edge)}
                    </span>
                    <span className="micro-label">conf {item.confidence.toFixed(1)}/10</span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
