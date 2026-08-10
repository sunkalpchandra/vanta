import { FeedExplorer } from "@/components/FeedExplorer";
import { MoversStrip } from "@/components/MoversStrip";
import { getFeed, getHistory, getMovers } from "@/lib/data";

export default async function FeedPage() {
  const [feed, movers] = await Promise.all([getFeed(), getMovers()]);
  const histories = await Promise.all(
    feed.map(async (card) => {
      const history = await getHistory(String(card.question_id));
      return [card.question_id, history.map((h) => h.probability)] as const;
    }),
  );
  const sparklines = new Map(histories);
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
        <FeedExplorer cards={feed} sparklines={Object.fromEntries(sparklines)} />
      )}
    </div>
  );
}
