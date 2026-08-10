import Link from "next/link";
import { notFound } from "next/navigation";
import { FeedExplorer } from "@/components/FeedExplorer";
import { StatTile } from "@/components/StatTile";
import { IS_STATIC } from "@/lib/config";
import { getCategories, getFeed, getLeaderboard } from "@/lib/data";
import { pct } from "@/lib/format";

const KNOWN = ["technology", "finance", "politics", "science", "sports", "crypto"];

export function generateStaticParams() {
  return IS_STATIC ? KNOWN.map((slug) => ({ slug })) : [];
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return { title: `${slug} — vanta` };
}

export default async function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [feed, categories, leaderboard] = await Promise.all([
    getFeed(),
    getCategories(),
    getLeaderboard(),
  ]);
  const meta = categories.find((c) => c.category === slug);
  if (!meta && !KNOWN.includes(slug)) notFound();
  const cards = feed.filter((c) => c.category === slug);
  const record = leaderboard.find((r) => r.category === slug);

  return (
    <div>
      <div className="mb-8">
        <div className="micro-label">category</div>
        <h1 className="mt-1 text-2xl font-bold capitalize tracking-tight">{slug}</h1>
      </div>
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatTile
          label="Long-run base rate"
          value={meta ? pct(meta.base_rate) : "—"}
          sub="how often questions like these resolve YES"
        />
        <StatTile
          label="Live questions"
          value={String(meta?.n_live_questions ?? cards.length)}
          sub={`${meta?.n_resolved ?? 0} resolved`}
        />
        <StatTile
          label="vanta accuracy here"
          value={record ? `${Math.round(record.vanta_accuracy * 100)}%` : "—"}
          tone="accent"
          sub={record ? `market ${Math.round(record.market_accuracy * 100)}%` : "no resolutions yet"}
        />
      </div>
      {cards.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No live questions in this category right now.
        </div>
      ) : (
        <FeedExplorer cards={cards} />
      )}
      <div className="mt-8">
        <Link href="/" className="text-sm text-accent hover:underline">
          ← All categories
        </Link>
      </div>
    </div>
  );
}
