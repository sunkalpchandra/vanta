import { describe, expect, it } from "vitest";
import { describeStrategy, getAgentTraders, type AgentTraderRow } from "./agentTraders";

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string }[] = [];
  const impl = (async (url: unknown) => {
    calls.push({ url: String(url) });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

describe("describeStrategy", () => {
  it("gives a distinct, non-empty blurb for each known strategy", () => {
    const edge = describeStrategy("edge");
    const confidence = describeStrategy("confidence");
    const contrarian = describeStrategy("contrarian");
    for (const s of [edge, confidence, contrarian]) {
      expect(s.length).toBeGreaterThan(0);
    }
    // All three read differently — no copy-paste collision.
    expect(new Set([edge, confidence, contrarian]).size).toBe(3);
  });

  it("names the confidence gate and the contrarian's cheap underdog", () => {
    expect(describeStrategy("confidence").toLowerCase()).toContain("confiden");
    expect(describeStrategy("contrarian").toLowerCase()).toMatch(/crowd|underdog|cheap/);
  });

  it("falls back to a stable generic line for an unknown strategy", () => {
    const s = describeStrategy("mystery");
    expect(s.length).toBeGreaterThan(0);
    expect(s).toBe(describeStrategy("also-unknown")); // same fallback for any unknown
    expect(s).not.toBe(describeStrategy("edge"));
  });
});

describe("getAgentTraders", () => {
  const rows: AgentTraderRow[] = [
    {
      name: "vanta-edge",
      strategy: "edge",
      equity: 10010,
      lifetime_pnl: 10,
      n_trades: 3,
      n_positions: 2,
      balance: 9950,
    },
  ];

  it("returns the parsed rows on 200 and hits the endpoint", async () => {
    const { impl, calls } = mockFetch(200, rows);
    const out = await getAgentTraders({ fetchImpl: impl });
    expect(out).toEqual(rows);
    expect(calls[0].url.endsWith("/api/agent-traders")).toBe(true);
  });

  it("returns [] on a non-2xx", async () => {
    const { impl } = mockFetch(500, { detail: "boom" });
    expect(await getAgentTraders({ fetchImpl: impl })).toEqual([]);
  });

  it("returns [] when the body is not an array", async () => {
    const { impl } = mockFetch(200, { oops: true });
    expect(await getAgentTraders({ fetchImpl: impl })).toEqual([]);
  });

  it("returns [] when the network throws", async () => {
    const impl = (() => {
      throw new Error("offline");
    }) as unknown as typeof fetch;
    expect(await getAgentTraders({ fetchImpl: impl })).toEqual([]);
  });
});
