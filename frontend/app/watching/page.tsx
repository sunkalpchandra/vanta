import { WatchingList } from "@/components/WatchingList";

export const metadata = { title: "watching — vanta" };

// The watchlist is per-trader and keyed to the X-API-Key held in the browser,
// so there is nothing to fetch server-side — WatchingList loads it client-side
// (and shows the no-identity / static-demo states honestly).
export default function WatchingPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Watching</h1>
        <p className="mt-1 text-sm text-ink-2">
          Your watched play-money markets and how they moved in the last 24h —
          play money · paper trading · real market prices.
        </p>
      </div>
      <WatchingList />
    </div>
  );
}
