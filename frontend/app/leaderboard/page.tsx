import Link from "next/link";
import { AccuracyChart } from "@/components/AccuracyChart";
import { CalibrationChart } from "@/components/CalibrationChart";
import { StatsBar } from "@/components/StatsBar";
import { getCalibration, getLeaderboard, getStats } from "@/lib/data";

export const metadata = { title: "accuracy — vanta" };

export default async function LeaderboardPage() {
  const [rows, stats, calibration] = await Promise.all([
    getLeaderboard(),
    getStats(),
    getCalibration(),
  ]);
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">vanta Accuracy</h1>
        <p className="mt-1 text-sm text-ink-2">
          Resolved-question track record by category — vanta vs the market&apos;s implied forecast.
          Lower Brier is better calibration.
        </p>
      </div>
      {stats && <div className="mb-4">{<StatsBar stats={stats} />}</div>}
      {rows.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No resolved predictions yet.</div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card p-5">
              <div className="micro-label mb-3">Directional accuracy by category</div>
              <AccuracyChart rows={rows} />
            </div>
            <div className="card p-5">
              <div className="micro-label mb-3">Calibration — observed vs predicted</div>
              <CalibrationChart bins={calibration} />
            </div>
          </div>
          <div className="card mt-4 overflow-x-auto">
            <table className="w-full min-w-[540px] text-sm">
              <thead>
                <tr className="border-b border-line text-left">
                  <th className="micro-label px-5 py-3 font-normal">Category</th>
                  <th className="micro-label px-5 py-3 text-right font-normal">Resolved</th>
                  <th className="micro-label px-5 py-3 text-right font-normal">vanta acc.</th>
                  <th className="micro-label px-5 py-3 text-right font-normal">Market acc.</th>
                  <th className="micro-label px-5 py-3 text-right font-normal">vanta Brier</th>
                  <th className="micro-label px-5 py-3 text-right font-normal">Market Brier</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const wins = row.vanta_accuracy >= row.market_accuracy;
                  return (
                    <tr key={row.category} className="border-b border-line/60 last:border-0">
                      <td className="px-5 py-3 font-medium capitalize">
                        <Link href={`/category/${row.category}`} className="text-ink hover:text-accent">
                          {row.category}
                        </Link>
                      </td>
                      <td className="num px-5 py-3 text-right text-ink-2">{row.n_resolved}</td>
                      <td className={`num px-5 py-3 text-right font-bold ${wins ? "text-pos" : "text-ink"}`}>
                        {(row.vanta_accuracy * 100).toFixed(0)}%
                        {/* win state must survive without color perception */}
                        {wins && (
                          <span className="ml-1">
                            ▲<span className="sr-only">vanta leads the market here</span>
                          </span>
                        )}
                      </td>
                      <td className="num px-5 py-3 text-right text-ink-2">
                        {(row.market_accuracy * 100).toFixed(0)}%
                      </td>
                      <td className="num px-5 py-3 text-right text-ink-2">{row.vanta_brier.toFixed(3)}</td>
                      <td className="num px-5 py-3 text-right text-ink-2">{row.market_brier.toFixed(3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted">
            Demo track record: seeded, deterministic data illustrating the intended edge. In production
            this table is written by the resolution pipeline as questions settle.
          </p>
        </>
      )}
    </div>
  );
}
