import { FeedExplorer } from "@/components/FeedExplorer";
import { MoversStrip } from "@/components/MoversStrip";
import { getFeed, getMovers, getSparklines } from "@/lib/data";

export default async function FeedPage() {
  // One payload for all sparklines instead of one history call per card.
  const [feed, movers, sparklines] = await Promise.all([getFeed(), getMovers(), getSparklines()]);
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Intelligence Feed</h1>
        <p className="mt-1 text-sm text-ink-2">
          Where vanta&apos;s agent pipeline most disagrees with prediction markets — ranked by edge.
        </p>
      </div>
      <MoversStrip movers={movers} />
      {feed.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">
          No intelligence available. Start the backend (<span className="num">uvicorn app.main:app</span>)
          and refresh — it seeds itself on first boot.
        </div>
      ) : (
        <FeedExplorer cards={feed} sparklines={sparklines} />
      )}
    </div>
  );
}
