import { describe, expect, it } from "vitest";
import { getMarketsTeaser, pickTopMovers } from "./marketsTeaser";
import type { MarketMover, MarketStats } from "./marketStats";

function mover(overrides: Partial<MarketMover> = {}): MarketMover {
  return {
    event_id: 1,
    question: "Will BTC close above $100k this year?",
    source: "polymarket",
    yes_price: 0.8,
    prev_price: 0.5,
    change: 0.3,
    volume_usd: 500,
    ...overrides,
  };
}

const STATS: MarketStats = {
  n_active: 12,
  n_settled: 34,
  by_source: { polymarket: 7, kalshi: 3, manifold: 2 },
  total_volume_usd: 1_234_567,
  n_traders: 5,
  n_open_positions: 9,
  n_trades: 88,
};

/** A fetch mock that routes stats vs movers by URL and records the calls. */
function routedFetch(routes: {
  stats?: { status: number; body: unknown };
  movers?: { status: number; body: unknown };
}) {
  const calls: string[] = [];
  const impl = (async (url: unknown) => {
    const u = String(url);
    calls.push(u);
    const r = u.includes("/movers") ? routes.movers : routes.stats;
    if (!r) throw new Error(`unrouted url ${u}`);
    return { ok: r.status >= 200 && r.status < 300, status: r.status, json: async () => r.body };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

describe("pickTopMovers", () => {
  it("returns the n biggest absolute moves, largest first", () => {
    const rows = [
      mover({ event_id: 1, change: 0.1 }),
      mover({ event_id: 2, change: -0.5 }),
      mover({ event_id: 3, change: 0.3 }),
      mover({ event_id: 4, change: -0.02 }),
    ];
    expect(pickTopMovers(rows, 2).map((m) => m.event_id)).toEqual([2, 3]);
  });

  it("ranks by magnitude regardless of sign", () => {
    const rows = [mover({ event_id: 1, change: 0.2 }), mover({ event_id: 2, change: -0.4 })];
    expect(pickTopMovers(rows, 1).map((m) => m.event_id)).toEqual([2]);
  });

  it("breaks ties by volume, then by lower event_id", () => {
    const rows = [
      mover({ event_id: 5, change: 0.2, volume_usd: 100 }),
      mover({ event_id: 3, change: -0.2, volume_usd: 900 }),
      mover({ event_id: 9, change: 0.2, volume_usd: 100 }),
    ];
    // Same magnitude: highest volume first (id 3), then equal-volume by lower id (5 before 9).
    expect(pickTopMovers(rows, 3).map((m) => m.event_id)).toEqual([3, 5, 9]);
  });

  it("sinks non-finite changes to the bottom instead of poisoning the sort", () => {
    const rows = [
      mover({ event_id: 1, change: Number.NaN }),
      mover({ event_id: 2, change: 0.1 }),
    ];
    expect(pickTopMovers(rows, 2).map((m) => m.event_id)).toEqual([2, 1]);
  });

  it("returns everything (still sorted) when n exceeds the length", () => {
    const rows = [mover({ event_id: 1, change: 0.1 }), mover({ event_id: 2, change: 0.4 })];
    expect(pickTopMovers(rows, 10).map((m) => m.event_id)).toEqual([2, 1]);
  });

  it("returns [] for n <= 0, an empty list, or a non-array", () => {
    expect(pickTopMovers([mover()], 0)).toEqual([]);
    expect(pickTopMovers([mover()], -3)).toEqual([]);
    expect(pickTopMovers([], 3)).toEqual([]);
    expect(pickTopMovers(undefined as unknown as MarketMover[], 3)).toEqual([]);
  });

  it("does not mutate its input", () => {
    const rows = [mover({ event_id: 1, change: 0.1 }), mover({ event_id: 2, change: 0.9 })];
    const snapshot = rows.map((m) => m.event_id);
    pickTopMovers(rows, 1);
    expect(rows.map((m) => m.event_id)).toEqual(snapshot);
  });
});

describe("getMarketsTeaser", () => {
  it("returns the surface stats and the top-n movers", async () => {
    const { impl, calls } = routedFetch({
      stats: { status: 200, body: STATS },
      movers: {
        status: 200,
        body: [
          mover({ event_id: 1, change: 0.1 }),
          mover({ event_id: 2, change: 0.5 }),
          mover({ event_id: 3, change: -0.3 }),
        ],
      },
    });
    const data = await getMarketsTeaser(2, { fetchImpl: impl });
    expect(data.stats?.n_active).toBe(12);
    expect(data.movers.map((m) => m.event_id)).toEqual([2, 3]);
    // Reuses the same 24h/limit-20 movers contract as the rest of the surface.
    expect(calls.some((u) => u.includes("window_hours=24&limit=20"))).toBe(true);
  });

  it("degrades stats to null but keeps movers on a stats-only failure", async () => {
    const { impl } = routedFetch({
      stats: { status: 500, body: {} },
      movers: { status: 200, body: [mover({ event_id: 7 })] },
    });
    const data = await getMarketsTeaser(3, { fetchImpl: impl });
    expect(data.stats).toBeNull();
    expect(data.movers.map((m) => m.event_id)).toEqual([7]);
  });

  it("propagates a movers-fetch failure so the caller can show an error", async () => {
    const { impl } = routedFetch({
      stats: { status: 200, body: STATS },
      movers: { status: 503, body: {} },
    });
    await expect(getMarketsTeaser(3, { fetchImpl: impl })).rejects.toThrow(/movers fetch failed \(503\)/);
  });
});
