const AGENTS = [
  {
    name: "Research Agent",
    role: "Weighs qualitative evidence for and against the event; tilts the market prior in log-odds space by the net signal.",
  },
  {
    name: "Quant Agent",
    role: "Matches the question against a corpus of resolved events (similarity-weighted hit rate), then runs a Beta-posterior Monte Carlo for the credible interval.",
  },
  {
    name: "Market Agent",
    role: "Reads the prediction-market consensus and decides how much to trust it from liquidity and volume.",
  },
  {
    name: "Sentiment Agent",
    role: "Public mood and momentum. A weak standalone predictor, so it enters the pool at low weight.",
  },
  {
    name: "Historian Agent",
    role: "Category base rates. Long horizons pull the market's current read toward the long-run frequency.",
  },
  {
    name: "Skeptic Agent",
    role: "Never estimates. Attacks the interim consensus — strongest opposing evidence, structural risks — and haircuts confidence by disagreement and evidence thinness.",
  },
  {
    name: "Synthesis Agent",
    role: "Pools every weighted estimate as a weighted average of log-odds, shrinks toward the base rate, and calibrates confidence from inter-agent agreement.",
  },
];

export const metadata = { title: "methodology — vanta" };

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Methodology</h1>
        <p className="mt-1 text-sm text-ink-2">
          How a vanta probability is made — and what it is not.
        </p>
      </div>

      <section className="card p-6">
        <div className="micro-label mb-3">The pipeline</div>
        <p className="text-sm leading-relaxed text-ink-2">
          Every question runs through seven independent reasoning modules. Five estimators produce
          probabilities with weights; the skeptic tries to break the emerging consensus; synthesis
          combines what survives. The debate is stored verbatim — every forecast on this site shows
          its full internal argument.
        </p>
        <ol className="mt-4 space-y-3">
          {AGENTS.map((agent, i) => (
            <li key={agent.name} className="flex gap-3">
              <span className="num w-5 shrink-0 text-right text-sm font-bold text-muted">{i + 1}</span>
              <div>
                <div className="text-sm font-semibold text-ink">{agent.name}</div>
                <p className="mt-0.5 text-sm leading-relaxed text-ink-2">{agent.role}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="card mt-4 p-6">
        <div className="micro-label mb-3">The math</div>
        <div className="space-y-3 text-sm leading-relaxed text-ink-2">
          <p>
            <strong className="text-ink">Log-odds pooling.</strong> Agent estimates combine as a
            weighted average of logits — a logarithmic opinion pool. Unlike averaging raw
            probabilities, this respects how evidence compounds near the extremes.
          </p>
          <p>
            <strong className="text-ink">Base-rate shrinkage.</strong> The pooled estimate is pulled
            mildly toward the category&apos;s long-run frequency, correcting the overconfidence that
            plagues both crowds and models.
          </p>
          <p>
            <strong className="text-ink">Monte Carlo uncertainty.</strong> Evidence strength sets the
            pseudo-sample size of a Beta posterior; sampling it yields the 90% credible interval and
            the probability that the true value sits above the market.
          </p>
          <p>
            <strong className="text-ink">Confidence, not just probability.</strong> The 0–10
            confidence score rises with inter-agent agreement and decisiveness, and falls with the
            skeptic&apos;s haircut. A 70% at confidence 8 and a 70% at confidence 3 are different
            claims.
          </p>
          <p>
            <strong className="text-ink">Scoring.</strong> Resolved questions are scored on
            directional accuracy and Brier score, and binned into the calibration curve on the
            accuracy page. Forecasts are only as good as their track record.
          </p>
        </div>
      </section>

      <section className="card mt-4 border-accent/30 p-6">
        <div className="micro-label mb-3">Honest limits</div>
        <p className="text-sm leading-relaxed text-ink-2">
          This deployment runs on a seeded demo corpus: market prices, evidence, and the resolved
          track record are deterministic fixtures that illustrate the system, not live data. The
          math is real; the edge is not yet earned. And when an LLM key is configured it writes the
          agents&apos; prose — never the numbers.
        </p>
      </section>
    </div>
  );
}
