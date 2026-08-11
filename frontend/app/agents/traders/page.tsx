import { AgentTraderBoard } from "@/components/AgentTraderBoard";
import { getAgentTraders, type AgentTraderRow } from "@/lib/agentTraders";
import { IS_STATIC } from "@/lib/config";

export const metadata = { title: "agent traders — vanta" };

/**
 * Load the agent-trader standings for the current mode.
 *
 * Live mode fetches the endpoint (via lib/agentTraders, which returns [] when
 * the backend is offline). Static mode reads the baked snapshot.
 *
 * INTEGRATION: the snapshot exporter should bake public/data/agent-traders.json
 * — the bare /api/agent-traders array — in lockstep with lib/data.ts, the same
 * rule every static surface follows. Until it does, static mode falls back to an
 * honest empty board rather than fabricating standings. The fs read stays in
 * this server-only module (lib/agentTraders.ts is client-safe and never imports
 * fs).
 */
async function loadRows(): Promise<AgentTraderRow[]> {
  if (IS_STATIC) {
    try {
      const { promises: fs } = await import("fs");
      const { join } = await import("path");
      const file = join(process.cwd(), "public", "data", "agent-traders.json");
      const body = JSON.parse(await fs.readFile(file, "utf8"));
      return Array.isArray(body) ? (body as AgentTraderRow[]) : [];
    } catch {
      return []; // not baked yet — honest empty
    }
  }
  return getAgentTraders();
}

export default async function AgentTradersPage() {
  const rows = await loadRows();
  return <AgentTraderBoard rows={rows} />;
}
