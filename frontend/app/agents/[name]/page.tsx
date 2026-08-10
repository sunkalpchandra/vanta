import Link from "next/link";
import { notFound } from "next/navigation";
import { IS_STATIC } from "@/lib/config";
import { getAgentRecords } from "@/lib/data";
import { pct } from "@/lib/format";

const KNOWN_AGENTS = ["research", "quant", "market", "sentiment", "historian", "synthesis"];

export function generateStaticParams() {
  return IS_STATIC ? KNOWN_AGENTS.map((name) => ({ name })) : [];
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  return { title: `${name} agent — vanta` };
}

export default async function AgentRecordsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  if (!KNOWN_AGENTS.includes(name)) notFound();
  const records = await getAgentRecords(name);
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8">
        <div className="micro-label">agent receipts</div>
        <h1 className="mt-1 text-2xl font-bold capitalize tracking-tight">{name} agent</h1>
        <p className="mt-1 text-sm text-ink-2">
          Every frozen call this agent made on a question that later resolved.
        </p>
      </div>
      {records.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No resolved calls yet.</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th className="micro-label px-5 py-3 font-normal">Question</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Call</th>
                <th className="micro-label px-5 py-3 text-center font-normal">Outcome</th>
                <th className="micro-label px-5 py-3 text-right font-normal">Abs. error</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={`${record.question_id}`} className="border-b border-line/60 last:border-0">
                  <td className="max-w-md px-5 py-3">
                    <Link
                      href={`/questions/${record.question_id}`}
                      className="text-ink transition-colors hover:text-accent"
                    >
                      {record.question}
                    </Link>
                  </td>
                  <td className="num px-5 py-3 text-right text-ink">{pct(record.probability)}</td>
                  <td className="px-5 py-3 text-center">
                    <span
                      className={`num rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                        record.outcome ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
                      }`}
                    >
                      {record.outcome ? "yes" : "no"}
                    </span>
                  </td>
                  <td className="num px-5 py-3 text-right text-ink-2">{record.abs_error.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-8">
        <Link href="/agents" className="text-sm text-accent hover:underline">
          ← Agent leaderboard
        </Link>
      </div>
    </div>
  );
}
