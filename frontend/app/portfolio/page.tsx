import { PortfolioView } from "@/components/PortfolioView";

export const metadata = { title: "portfolio — vanta" };

export default function PortfolioPage() {
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
    </div>
  );
}
