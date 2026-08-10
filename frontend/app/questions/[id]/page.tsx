import Link from "next/link";
import { notFound } from "next/navigation";
import { CategoryBadge, EdgeBadge } from "@/components/Badges";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { DebatePanel } from "@/components/DebatePanel";
import { EvidenceList } from "@/components/EvidenceList";
import { ProbabilityChart } from "@/components/ProbabilityChart";
import { StatTile } from "@/components/StatTile";
import { API_URL, getHistory, getQuestion } from "@/lib/api";
import { pct, signedPct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function QuestionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [detail, history] = await Promise.all([getQuestion(id), getHistory(id)]);
  if (!detail) notFound();
  const forecast = detail.latest_forecast;
  const edge = forecast ? forecast.probability - detail.market_probability : 0;

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <CategoryBadge category={detail.category} />
          <span className="micro-label">{detail.horizon_days}d horizon</span>
          <span className="micro-label">
            · ${Math.round(detail.market_volume_usd).toLocaleString()} market volume ·{" "}
            {detail.market_liquidity} liquidity
          </span>
        </div>
        <h1 className="mt-3 max-w-3xl text-2xl font-bold leading-snug tracking-tight">
          {detail.question}
        </h1>
      </div>

      {forecast && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatTile label="Market probability" value={pct(detail.market_probability)} />
            <StatTile label="vanta prediction" value={pct(forecast.probability)} tone="accent" />
            <StatTile
              label="vanta edge"
              value={signedPct(edge)}
              tone={edge >= 0 ? "pos" : "neg"}
              sub="positive = market underpricing"
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="card p-5 lg:col-span-2">
              <div className="micro-label mb-3">Forecast history — 30 days</div>
              <ProbabilityChart history={history} marketProbability={detail.market_probability} />
            </div>
            <div className="card flex flex-col justify-between gap-6 p-5">
              <ConfidenceMeter value={forecast.confidence} />
              <div>
                <div className="micro-label mb-2">Risk factors</div>
                <ul className="space-y-1.5">
                  {(forecast.risk_factors as string[]).slice(0, 4).map((risk, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-2">
                      <span className="text-neg">▸</span>
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
              <a
                href={`${API_URL}/api/cards/${detail.id}.svg`}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg border border-line px-4 py-2 text-center text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
              >
                Share card ↗
              </a>
            </div>
          </div>

          <div className="card mt-4 p-5">
            <div className="micro-label mb-2">Synthesis reasoning</div>
            <p className="text-sm leading-relaxed text-ink-2">{forecast.reasoning}</p>
          </div>
        </>
      )}

      <div className="mt-10 grid gap-8 lg:grid-cols-5">
        <section className="lg:col-span-3">
          <h2 className="mb-1 text-lg font-bold">Agent debate</h2>
          <p className="mb-4 text-sm text-muted">
            Every forecast is an argument. Seven agents deliberate; the skeptic attacks; synthesis pools.
          </p>
          <DebatePanel reports={detail.agent_reports} />
        </section>
        <section className="lg:col-span-2">
          <h2 className="mb-1 text-lg font-bold">Evidence</h2>
          <p className="mb-4 text-sm text-muted">Signals ingested for this question, by impact.</p>
          <EvidenceList evidence={detail.evidence} />
        </section>
      </div>

      <div className="mt-10">
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Back to feed
        </Link>
      </div>
    </div>
  );
}
