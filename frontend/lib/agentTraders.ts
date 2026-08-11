// Play-money agent-trader dashboard access + a pure strategy blurb. Client-safe:
// the only runtime import is API_URL, so both server and client components can
// import from here (the page reads the baked snapshot itself in static mode —
// this module never imports fs). Play money only — virtual ⓥ credits, paper
// trading at real synced venue prices, never real money.

import { API_URL } from "./api";

/** One agent-trader's live standing — mirrors a /api/agent-traders row. */
export interface AgentTraderRow {
  name: string;
  strategy: string; // edge | confidence | contrarian
  equity: number; // cash + market value of open positions
  lifetime_pnl: number; // equity above the ⓥ10,000 starting bankroll
  n_trades: number;
  n_positions: number; // open (unsettled, still-held) positions
  balance: number; // uninvested cash
}

/**
 * Fetch vanta's agent-trader standings. Returns [] on any non-2xx, a
 * non-array body, or a network failure, so callers render their empty state
 * instead of throwing. Live API only — static mode reads the baked snapshot in
 * the page (a server-only module).
 */
export async function getAgentTraders(
  deps: { fetchImpl?: typeof fetch } = {},
): Promise<AgentTraderRow[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  try {
    const res = await doFetch(`${API_URL}/api/agent-traders`);
    if (!res.ok) return [];
    const body = await res.json();
    return Array.isArray(body) ? (body as AgentTraderRow[]) : [];
  } catch {
    return []; // backend offline — caller renders its empty state
  }
}

// --- pure display helpers (deterministic, unit-tested) ----------------------

/**
 * Human blurb for a bot's deterministic strategy — the edge it bets and the
 * gate that fires it, in plain language. Unknown strategies fall back to a
 * generic honest line (never an empty string).
 */
export function describeStrategy(strategy: string): string {
  switch (strategy) {
    case "edge":
      return "Backs vanta's forecast whenever it diverges from the venue price by at least 8 points — buys the side the pipeline reads as mispriced.";
    case "confidence":
      return "Takes the same side as the edge bot, but only when the pipeline is confident (7 out of 10 or higher), and stakes more the surer it is.";
    case "contrarian":
      return "Fades the crowd — buys the cheap underdog the market prices under 50%, but only when vanta agrees it is underpriced by 10 points or more.";
    default:
      return "A deterministic play-money strategy trading vanta's own forecasts.";
  }
}
