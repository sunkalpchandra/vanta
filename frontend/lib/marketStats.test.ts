import { describe, expect, it } from "vitest";
import {
  formatCompactUsd,
  formatMoverDelta,
  getMarketStats,
  getMovers,
  moverTone,
  type MarketMover,
  type MarketStats,
} from "./marketStats";

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string }[] = [];
  const impl = (async (url: unknown) => {
    calls.push({ url: String(url) });
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

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

describe("formatMoverDelta", () => {
  it("marks an up move with ▲ and an explicit +", () => {
    expect(formatMoverDelta(0.3)).toBe("▲ +30%");
    expect(formatMoverDelta(0.05)).toBe("▲ +5%");
  });

  it("marks a down move with ▼ and the number's own minus", () => {
    expect(formatMoverDelta(-0.4)).toBe("▼ -40%");
    expect(formatMoverDelta(-0.123)).toBe("▼ -12%");
  });

  it("renders a sub-half-percent move as a flat 0%", () => {
    expect(formatMoverDelta(0.004)).toBe("→ 0%");
    expect(formatMoverDelta(0)).toBe("→ 0%");
    expect(formatMoverDelta(-0.002)).toBe("→ 0%");
  });

  it("rounds to a whole percent", () => {
    expect(formatMoverDelta(0.126)).toBe("▲ +13%");
    expect(formatMoverDelta(-0.126)).toBe("▼ -13%");
  });
});

describe("moverTone", () => {
  it("agrees with the label: pos / neg / flat on the rounded move", () => {
    expect(moverTone(0.3)).toBe("pos");
    expect(moverTone(-0.4)).toBe("neg");
    expect(moverTone(0)).toBe("flat");
    // A move that rounds to 0% reads flat, so the color can't contradict the text.
    expect(moverTone(0.004)).toBe("flat");
  });
});

describe("formatCompactUsd", () => {
  it("scales into K / M / B with one decimal", () => {
    expect(formatCompactUsd(1234)).toBe("$1.2K");
    expect(formatCompactUsd(1_500_000)).toBe("$1.5M");
    expect(formatCompactUsd(2_000_000_000)).toBe("$2B");
  });

  it("trims a trailing .0 and prints whole dollars below 1K", () => {
    expect(formatCompactUsd(5000)).toBe("$5K");
    expect(formatCompactUsd(950)).toBe("$950");
    expect(formatCompactUsd(0)).toBe("$0");
    expect(formatCompactUsd(12.4)).toBe("$12");
  });
});

describe("getMarketStats", () => {
  it("fetches the stats endpoint and returns the object", async () => {
    const { impl, calls } = mockFetch(200, STATS);
    const stats = await getMarketStats({ fetchImpl: impl });
    expect(stats.n_active).toBe(12);
    expect(stats.by_source.kalshi).toBe(3);
    expect(calls[0].url.endsWith("/api/market-stats")).toBe(true);
  });

  it("throws on a non-ok response", async () => {
    const { impl } = mockFetch(500, {});
    await expect(getMarketStats({ fetchImpl: impl })).rejects.toThrow(/market stats fetch failed \(500\)/);
  });
});

describe("getMovers", () => {
  it("fetches a bare list with the window + limit in the query", async () => {
    const { impl, calls } = mockFetch(200, [mover(), mover({ event_id: 2 })]);
    const movers = await getMovers(24, 20, { fetchImpl: impl });
    expect(movers).toHaveLength(2);
    expect(movers[0].event_id).toBe(1);
    expect(calls[0].url.endsWith("/api/market-stats/movers?window_hours=24&limit=20")).toBe(true);
  });

  it("passes a custom window and limit through", async () => {
    const { impl, calls } = mockFetch(200, []);
    await getMovers(72, 5, { fetchImpl: impl });
    expect(calls[0].url.endsWith("/api/market-stats/movers?window_hours=72&limit=5")).toBe(true);
  });

  it("tolerates an object envelope { movers: [...] }", async () => {
    const { impl } = mockFetch(200, { movers: [mover({ event_id: 9 })] });
    const movers = await getMovers(24, 20, { fetchImpl: impl });
    expect(movers.map((m) => m.event_id)).toEqual([9]);
  });

  it("returns [] when an envelope carries no movers", async () => {
    const { impl } = mockFetch(200, { note: "play money" });
    expect(await getMovers(24, 20, { fetchImpl: impl })).toEqual([]);
  });

  it("throws on a non-ok response", async () => {
    const { impl } = mockFetch(503, {});
    await expect(getMovers(24, 20, { fetchImpl: impl })).rejects.toThrow(/movers fetch failed \(503\)/);
  });
});
