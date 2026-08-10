import { getPredictions } from "@/lib/data";
import { pct, shortDate } from "@/lib/format";

export const metadata = { title: "archive — vanta" };

export default async function ArchivePage() {
  const predictions = await getPredictions();
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Archive</h1>
        <p className="mt-1 text-sm text-ink-2">
          Every settled call — vanta&apos;s frozen forecast vs the market&apos;s, against what
          actually happened. Closer call is marked.
        </p>
      </div>
      {predictions.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">Nothing has resolved yet.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="micro-label px-5 py-3 font-normal">Question</th>
                <th className="micro-label px-5 py-3 font-normal">Category</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Market</th>
                <th className="micro-label px-5 py-3 text-right font-normal">vanta</th>
                <th className="micro-label px-5 py-3 text-center font-normal">Outcome</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Resolved</th>
              </tr>
            </thead>
            <tbody>
              {predictions.map((p, i) => {
                const vantaCloser =
                  Math.abs(p.vanta_probability - p.outcome) < Math.abs(p.market_probability - p.outcome);
                return (
                  <tr key={i} className="border-b border-line/60 last:border-0">
                    <td className="max-w-md px-5 py-3 text-ink">{p.question_text}</td>
                    <td className="px-5 py-3 capitalize text-ink-2">{p.category}</td>
                    <td className="num px-5 py-3 text-right text-ink-2">
                      {pct(p.market_probability)}
                      {!vantaCloser && <span className="ml-1 text-accent-2" title="closer call">●</span>}
                    </td>
                    <td className="num px-5 py-3 text-right text-ink">
                      {pct(p.vanta_probability)}
                      {vantaCloser && <span className="ml-1 text-accent" title="closer call">●</span>}
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span
                        className={`num rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                          p.outcome ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
                        }`}
                      >
                        {p.outcome ? "yes" : "no"}
                      </span>
                    </td>
                    <td className="num px-5 py-3 text-right text-ink-2">{shortDate(p.resolved_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        ● marks whose probability sat closer to the realized outcome. The seeded rows are demo
        fixtures; rows with a question link were resolved live through the API.
      </p>
    </div>
  );
}
