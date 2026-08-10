import { TradeHistory } from "@/components/TradeHistory";

export const metadata = { title: "trade history — vanta" };

// Server shell only — the caller's book is identity-scoped (X-API-Key held in
// the browser), so all fetching happens client-side in <TradeHistory/>. In
// static mode the component shows an honest "connect the backend" empty state.
export default function HistoryPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Trade history</h1>
        <p className="mt-1 text-sm text-ink-2">
          Every play-money execution you&apos;ve placed, plus CSV exports of your trades and
          positions — play money · paper trading · real market prices.
        </p>
      </div>
      <TradeHistory />
    </div>
  );
}
