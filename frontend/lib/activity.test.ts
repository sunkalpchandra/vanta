import { describe, expect, it } from "vitest";
import { formatTapeLine, getActivity, type TradeTapeItem } from "./activity";

function item(overrides: Partial<TradeTapeItem> = {}): TradeTapeItem {
  return {
    id: 1,
    trader: "alice",
    event_id: 7,
    question: "Will BTC close above $100k this year?",
    side: "yes",
    action: "buy",
    shares: 100,
    price: 0.42,
    created_at: "2026-08-10T00:00:00Z",
    ...overrides,
  };
}

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string }[] = [];
  const impl = (async (url: unknown) => {
    calls.push({ url: String(url) });
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

describe("formatTapeLine", () => {
  it("formats a buy the way the tape reads", () => {
    expect(formatTapeLine(item())).toBe(
      "alice bought 100 YES @ 42% · Will BTC close above $100k this year?",
    );
  });

  it("says 'sold' and uppercases the NO side", () => {
    expect(formatTapeLine(item({ trader: "bob", action: "sell", side: "no", shares: 50, price: 0.626 }))).toBe(
      "bob sold 50 NO @ 63% · Will BTC close above $100k this year?",
    );
  });

  it("rounds the price to a whole percent", () => {
    expect(formatTapeLine(item({ price: 0.014 }))).toContain("@ 1%");
    expect(formatTapeLine(item({ price: 0.996 }))).toContain("@ 100%");
  });

  it("keeps fractional-share lots to 2 decimals, whole lots bare", () => {
    expect(formatTapeLine(item({ shares: 12.5 }))).toContain("bought 12.5 YES");
    expect(formatTapeLine(item({ shares: 0.013 }))).toContain("bought 0.01 YES");
    expect(formatTapeLine(item({ shares: 100 }))).toContain("bought 100 YES");
  });

  it("truncates a long question with an ellipsis, bounded to maxQuestion", () => {
    const line = formatTapeLine(item({ question: "x".repeat(80) }));
    const questionPart = line.split(" · ")[1];
    expect(questionPart.endsWith("…")).toBe(true);
    expect(questionPart.length).toBe(48); // 47 chars + ellipsis
  });

  it("respects a custom maxQuestion", () => {
    const line = formatTapeLine(item({ question: "y".repeat(40) }), 10);
    expect(line.split(" · ")[1]).toBe(`${"y".repeat(9)}…`);
  });
});

describe("getActivity", () => {
  it("fetches the live feed and unwraps the envelope", async () => {
    const { impl, calls } = mockFetch(200, { trades: [item(), item({ id: 2 })], note: "play money" });
    const trades = await getActivity(30, { fetchImpl: impl });
    expect(trades).toHaveLength(2);
    expect(trades[0].id).toBe(1);
    expect(calls[0].url.endsWith("/api/activity/trades?limit=30")).toBe(true);
  });

  it("passes a custom limit through", async () => {
    const { impl, calls } = mockFetch(200, { trades: [] });
    await getActivity(5, { fetchImpl: impl });
    expect(calls[0].url.endsWith("/api/activity/trades?limit=5")).toBe(true);
  });

  it("returns [] when the envelope has no trades", async () => {
    const { impl } = mockFetch(200, { note: "play money" });
    expect(await getActivity(30, { fetchImpl: impl })).toEqual([]);
  });

  it("throws on a non-ok response", async () => {
    const { impl } = mockFetch(500, {});
    await expect(getActivity(30, { fetchImpl: impl })).rejects.toThrow(/activity fetch failed \(500\)/);
  });
});
