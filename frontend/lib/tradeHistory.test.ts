import { describe, expect, it } from "vitest";
import type { TradeRow } from "./tradeHistory";
import { getTradeHistory, summarize } from "./tradeHistory";

function memoryStorage(initial: string | null = null) {
  let value = initial;
  return {
    getItem: () => value,
    setItem: (_: string, v: string) => {
      value = v;
    },
    removeItem: () => {
      value = null;
    },
  };
}

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const impl = (async (url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

function trade(over: Partial<TradeRow> = {}): TradeRow {
  return {
    id: 1,
    event_id: 10,
    side: "yes",
    action: "buy",
    shares: 100,
    price: 0.4,
    cost: -40,
    created_at: "2026-08-10T00:00:00Z",
    ...over,
  };
}

describe("summarize", () => {
  it("is empty for no trades", () => {
    expect(summarize([])).toEqual({ n: 0, volume: 0, buys: 0, sells: 0 });
  });

  it("counts executions and sums notional (shares × price)", () => {
    const trades = [
      trade({ id: 1, action: "buy", shares: 100, price: 0.4 }), // 40
      trade({ id: 2, action: "buy", shares: 50, price: 0.5 }), // 25
      trade({ id: 3, action: "sell", shares: 30, price: 0.6 }), // 18
    ];
    expect(summarize(trades)).toEqual({ n: 3, volume: 83, buys: 2, sells: 1 });
  });

  it("rounds volume once, to the cent, house-agnostic", () => {
    // 3 × 0.333 = 0.999 → 1.00 after a single round2.
    expect(summarize([trade({ shares: 3, price: 0.333 })]).volume).toBe(1);
  });

  it("keeps buys + sells equal to n", () => {
    const trades = [trade({ action: "buy" }), trade({ action: "sell" }), trade({ action: "sell" })];
    const s = summarize(trades);
    expect(s.buys + s.sells).toBe(s.n);
    expect(s).toMatchObject({ buys: 1, sells: 2, n: 3 });
  });
});

describe("getTradeHistory", () => {
  it("returns recent_trades from the portfolio endpoint with the key header", async () => {
    const storage = memoryStorage("vk_hist");
    const rows = [trade({ id: 7 })];
    const { impl, calls } = mockFetch(200, { balance: 10000, recent_trades: rows });
    const out = await getTradeHistory({ storage, fetchImpl: impl });
    expect(out).toEqual(rows);
    expect(calls).toHaveLength(1);
    expect(calls[0].url.endsWith("/api/markets/portfolio/me")).toBe(true);
    expect(calls[0].init?.headers).toEqual({ "X-API-Key": "vk_hist" });
  });

  it("defaults to an empty list when recent_trades is absent", async () => {
    const { impl } = mockFetch(200, { balance: 10000 });
    expect(await getTradeHistory({ storage: memoryStorage("vk_x"), fetchImpl: impl })).toEqual([]);
  });

  it("throws a readable error on a non-ok response", async () => {
    const { impl } = mockFetch(401, { detail: "invalid API key" });
    await expect(
      getTradeHistory({ storage: memoryStorage("vk_bad"), fetchImpl: impl }),
    ).rejects.toThrow(/401/);
  });
});
