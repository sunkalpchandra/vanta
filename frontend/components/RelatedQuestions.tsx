import Link from "next/link";
import { getRelated } from "@/lib/data";

export async function RelatedQuestions({ questionId }: { questionId: number }) {
  const related = await getRelated(String(questionId));
  if (!related.length) return null;
  return (
    <div className="card mt-4 p-5">
      <div className="micro-label mb-3">Related questions</div>
      <ul className="space-y-2">
        {related.map((r) => (
          <li key={r.id} className="flex items-center gap-3">
            <Link
              href={`/questions/${r.id}`}
              className="min-w-0 flex-1 truncate text-sm text-ink-2 transition-colors hover:text-ink"
              title={r.question}
            >
              {r.question}
            </Link>
            {r.resolved && (
              <span className="micro-label shrink-0 rounded border border-line px-1.5 py-0.5">
                resolved
              </span>
            )}
            <span className="num w-10 shrink-0 text-right text-xs text-muted">
              {Math.round(r.similarity * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
