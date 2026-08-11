import { describe, expect, it } from "vitest";
import {
  getArchive,
  marketCalledIt,
  type ArchiveItem,
  type ArchiveOut,
} from "./marketArchive";

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string }[] = [];
  const impl = (async (url: unknown) => {
    calls.push({ url: String(url) });
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

function item(overrides: Partial<ArchiveItem> = {}): ArchiveItem {
  return {
    event_id: 1,
    question: "Will BTC close above $100k this year?",
    category: "crypto",
    source: "polymarket",
    outcome: 1,
    final_price: 0.82,
    close_time: "2026-01-01T00:00:00Z",
    volume_usd: 5000,
    ...overrides,
  };
}

describe("marketCalledIt", () => {
  it("is true when a YES-leaning final price resolved YES", () => {
    expect(marketCalledIt({ final_price: 0.82, outcome: 1 })).toBe(true);
    expect(marketCalledIt({ final_price: 0.51, outcome: 1 })).toBe(true);
  });

  it("is true when a NO-leaning final price resolved NO", () => {
    expect(marketCalledIt({ final_price: 0.3, outcome: 0 })).toBe(true);
    expect(marketCalledIt({ final_price: 0.49, outcome: 0 })).toBe(true);
  });

  it("is false when the final price leaned the wrong way", () => {
    // Market leaned YES (>0.5) but it resolved NO.
    expect(marketCalledIt({ final_price: 0.71, outcome: 0 })).toBe(false);
    // Market leaned NO (<=0.5) but it resolved YES.
    expect(marketCalledIt({ final_price: 0.2, outcome: 1 })).toBe(false);
  });

  it("treats exactly 0.5 as a NO lean (strictly > 0.5 is YES)", () => {
    expect(marketCalledIt({ final_price: 0.5, outcome: 0 })).toBe(true);
    expect(marketCalledIt({ final_price: 0.5, outcome: 1 })).toBe(false);
  });

  it("is null when the outcome or the final price is missing", () => {
    expect(marketCalledIt({ final_price: 0.82, outcome: null })).toBeNull();
    expect(marketCalledIt({ final_price: null, outcome: 1 })).toBeNull();
    expect(marketCalledIt({ final_price: null, outcome: null })).toBeNull();
  });
});

describe("getArchive", () => {
  it("fetches with limit + offset in the query and returns the envelope", async () => {
    const out: ArchiveOut = { total: 2, items: [item(), item({ event_id: 2 })] };
    const { impl, calls } = mockFetch(200, out);
    const result = await getArchive({ limit: 50, offset: 0, fetchImpl: impl });
    expect(result.total).toBe(2);
    expect(result.items).toHaveLength(2);
    expect(calls[0].url).toContain("/api/market-archive?");
    expect(calls[0].url).toContain("limit=50");
    expect(calls[0].url).toContain("offset=0");
  });

  it("adds a category param when one is given, and offsets forward", async () => {
    const { impl, calls } = mockFetch(200, { total: 0, items: [] });
    await getArchive({ category: "crypto", limit: 25, offset: 25, fetchImpl: impl });
    expect(calls[0].url).toContain("category=crypto");
    expect(calls[0].url).toContain("limit=25");
    expect(calls[0].url).toContain("offset=25");
  });

  it("omits the category param for the 'all' pseudo-category", async () => {
    const { impl, calls } = mockFetch(200, { total: 0, items: [] });
    await getArchive({ category: "all", fetchImpl: impl });
    expect(calls[0].url).not.toContain("category=");
  });

  it("tolerates a bare list response, deriving total from its length", async () => {
    const { impl } = mockFetch(200, [item({ event_id: 9 }), item({ event_id: 10 })]);
    const result = await getArchive({ fetchImpl: impl });
    expect(result.total).toBe(2);
    expect(result.items.map((r) => r.event_id)).toEqual([9, 10]);
  });

  it("throws a readable error on a non-ok response", async () => {
    const { impl } = mockFetch(503, {});
    await expect(getArchive({ fetchImpl: impl })).rejects.toThrow(/archive fetch failed \(503\)/);
  });
});
