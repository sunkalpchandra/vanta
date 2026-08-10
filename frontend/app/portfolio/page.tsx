import { PortfolioView } from "@/components/PortfolioView";
import { TraderLeaderboard } from "@/components/TraderLeaderboard";
import { getTraderBoard } from "@/lib/data";

export const metadata = { title: "portfolio — vanta" };

export default async function PortfolioPage() {
  const board = await getTraderBoard();
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Portfolio</h1>
        <p className="mt-1 text-sm text-ink-2">
          Your play-money book, marked to the latest synced venue prices —
          play money · paper trading · real market prices.
        </p>
      </div>
      <PortfolioView />
      <section className="mt-10">
        <div className="micro-label mb-3">Trader leaderboard — lifetime P&amp;L vs ⓥ10,000</div>
        <TraderLeaderboard board={board} />
      </section>
    </div>
  );
}
