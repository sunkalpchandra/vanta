import { notFound } from "next/navigation";
import { TraderProfile, type TraderProfileView } from "@/components/TraderProfile";
import { IS_STATIC } from "@/lib/config";
import { getTraderBoard } from "@/lib/data";
import { getTraderProfile } from "@/lib/traderProfile";

// Everyone starts at ⓥ10,000; lifetime P&L is equity above that line — the same
// definition the leaderboard ranks by (trading.STARTING_BALANCE).
const STARTING_BALANCE = 10_000;

/** Static export: bake one page per trader in the snapshot leaderboard. Live
 * mode returns [] and renders profiles on demand (same pattern as agents). */
export async function generateStaticParams() {
  if (!IS_STATIC) return [];
  const board = await getTraderBoard();
  return (board?.traders ?? []).map((t) => ({ name: t.name }));
}

export async function generateMetadata({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  return { title: `${name} — trader — vanta` };
}

export default async function TraderProfilePage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = await params;

  // Static mode has no live backend for position detail: render a lightweight
  // header from the baked leaderboard row and say so honestly.
  if (IS_STATIC) {
    const board = await getTraderBoard();
    const row = (board?.traders ?? []).find((t) => t.name === name);
    if (!row) notFound();
    const view: TraderProfileView = {
      name: row.name,
      joined: null,
      balance: null,
      equity: row.equity,
      lifetimePnl: row.lifetime_pnl,
      realizedPnl: null,
      nTrades: row.n_trades,
      positions: [],
      recentTrades: [],
      isStatic: true,
    };
    return <TraderProfile view={view} />;
  }

  const profile = await getTraderProfile(name);
  if (!profile) notFound();
  const view: TraderProfileView = {
    name: profile.name,
    joined: profile.joined,
    balance: profile.balance,
    equity: profile.equity,
    lifetimePnl: profile.equity - STARTING_BALANCE,
    realizedPnl: profile.realized_pnl,
    nTrades: profile.n_trades,
    positions: profile.positions,
    recentTrades: profile.recent_trades,
    isStatic: false,
  };
  return <TraderProfile view={view} />;
}
