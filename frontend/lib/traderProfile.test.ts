import { describe, expect, it } from "vitest";
import { getTraderProfile, pnlColor, winRate, type ProfilePosition } from "./traderProfile";

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

function pos(over: Partial<ProfilePosition> = {}): ProfilePosition {
  return {
    event_id: 1,
    question: "Will it resolve YES?",
    side: "yes",
    shares: 10,
    avg_price: 0.4,
    current_price: 0.5,
    unrealized_pnl: 1,
    settled: false,
    ...over,
  };
}

describe("pnlColor", () => {
  it("greens non-negative, reds negative", () => {
    expect(pnlColor(0)).toBe("text-pos");
    expect(pnlColor(12.5)).toBe("text-pos");
    expect(pnlColor(-0.01)).toBe("text-neg");
    expect(pnlColor(-99)).toBe("text-neg");
  });
});

describe("winRate", () => {
  it("is the share of marked-open positions in profit", () => {
    const positions = [
      pos({ unrealized_pnl: 5 }),
      pos({ event_id: 2, unrealized_pnl: -2 }),
      pos({ event_id: 3, unrealized_pnl: 3 }),
    ];
    expect(winRate(positions)).toBeCloseTo(2 / 3, 10);
  });

  it("ignores settled, closed, and unmarked positions", () => {
    const positions = [
      pos({ settled: true, unrealized_pnl: 9 }), // settled
      pos({ event_id: 2, shares: 0, unrealized_pnl: 9 }), // closed
      pos({ event_id: 3, unrealized_pnl: null }), // no mark
      pos({ event_id: 4, unrealized_pnl: 4 }), // the only qualifier — green
    ];
    expect(winRate(positions)).toBe(1);
  });

  it("counts a flat (zero) mark as not a win", () => {
    expect(winRate([pos({ unrealized_pnl: 0 })])).toBe(0);
  });

  it("returns null when nothing qualifies", () => {
    expect(winRate([])).toBeNull();
    expect(winRate([pos({ settled: true })])).toBeNull();
    expect(winRate([pos({ shares: 0 })])).toBeNull();
  });
});

describe("getTraderProfile", () => {
  const body = {
    name: "alice",
    joined: "2026-08-10T00:00:00Z",
    balance: 9960,
    equity: 10010,
    realized_pnl: 0,
    n_trades: 3,
    positions: [],
    recent_trades: [],
  };

  it("returns the parsed profile on 200 and hits the handle URL", async () => {
    const { impl, calls } = mockFetch(200, body);
    const profile = await getTraderProfile("alice", { fetchImpl: impl });
    expect(profile?.name).toBe("alice");
    expect(profile?.equity).toBe(10010);
    expect(calls[0].url.endsWith("/api/traders/alice")).toBe(true);
  });

  it("URL-encodes the handle", async () => {
    const { impl, calls } = mockFetch(200, body);
    await getTraderProfile("a b/c", { fetchImpl: impl });
    expect(calls[0].url.endsWith("/api/traders/a%20b%2Fc")).toBe(true);
  });

  it("returns null on 404", async () => {
    const { impl } = mockFetch(404, { detail: "trader not found" });
    expect(await getTraderProfile("ghost", { fetchImpl: impl })).toBeNull();
  });

  it("returns null when the network throws", async () => {
    const impl = (() => {
      throw new Error("offline");
    }) as unknown as typeof fetch;
    expect(await getTraderProfile("x", { fetchImpl: impl })).toBeNull();
  });
});
