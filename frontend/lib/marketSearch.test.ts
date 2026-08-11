import { describe, expect, it } from "vitest";
import {
  highlightMatch,
  searchMarkets,
  searchSample,
  type SearchHit,
} from "./marketSearch";
import type { MarketItem } from "./types";

function market(overrides: Partial<MarketItem> = {}): MarketItem {
  return {
    id: 1,
    question: "Will BTC close above $100k this year?",
    category: "crypto",
    source: "polymarket",
    yes_price: 0.8,
    volume_usd: 500,
    close_time: null,
    outcome: null,
    ...overrides,
  };
}

describe("highlightMatch", () => {
  it("splits around a single case-insensitive match, preserving original casing", () => {
    const parts = highlightMatch("Will BTC hit 100k?", "btc");
    expect(parts).toEqual([
      { text: "Will ", match: false },
      { text: "BTC", match: true }, // matched run keeps the source's casing
      { text: " hit 100k?", match: false },
    ]);
    // The matched run keeps the source's casing, not the query's.
    expect(parts.find((p) => p.match)?.text).toBe("BTC");
  });

  it("flags every occurrence", () => {
    const parts = highlightMatch("rate cut then another rate cut", "rate");
    expect(parts.filter((p) => p.match).map((p) => p.text)).toEqual(["rate", "rate"]);
    // Reassembling the parts reproduces the source exactly.
    expect(parts.map((p) => p.text).join("")).toBe("rate cut then another rate cut");
  });

  it("returns one unmatched run when the query never occurs", () => {
    expect(highlightMatch("Fed decision in March", "bitcoin")).toEqual([
      { text: "Fed decision in March", match: false },
    ]);
  });

  it("treats a blank or whitespace-only query as no match", () => {
    expect(highlightMatch("anything", "")).toEqual([{ text: "anything", match: false }]);
    expect(highlightMatch("anything", "   ")).toEqual([{ text: "anything", match: false }]);
  });

  it("returns [] for an empty question", () => {
    expect(highlightMatch("", "x")).toEqual([]);
  });

  it("handles a match at the very start and very end", () => {
    expect(highlightMatch("SpaceX launch", "spacex")).toEqual([
      { text: "SpaceX", match: true },
      { text: " launch", match: false },
    ]);
    expect(highlightMatch("launch SpaceX", "spacex")).toEqual([
      { text: "launch ", match: false },
      { text: "SpaceX", match: true },
    ]);
  });

  it("treats regex metacharacters in the query as literal text", () => {
    expect(highlightMatch("gain of +30% expected", "+30%")).toEqual([
      { text: "gain of ", match: false },
      { text: "+30%", match: true },
      { text: " expected", match: false },
    ]);
  });

  it("reassembles to the original for any input", () => {
    const q = "Will the S&P 500 close above 6000?";
    expect(highlightMatch(q, "500").map((p) => p.text).join("")).toBe(q);
  });
});

describe("searchSample", () => {
  const rows: MarketItem[] = [
    market({ id: 1, question: "Will BTC top $100k?", volume_usd: 100, outcome: null }),
    market({ id: 2, question: "Will BTC top $200k?", volume_usd: 900, outcome: null }),
    market({ id: 3, question: "Did BTC top $50k in 2020?", volume_usd: 5000, outcome: 1 }),
    market({ id: 4, question: "Will ETH flip to number one?", volume_usd: 400, outcome: null }),
    market({ id: 5, question: "Fed cuts rates in March?", volume_usd: 800, outcome: null }),
  ];

  it("substring-matches case-insensitively and defaults to active-only", () => {
    const ids = searchSample(rows, "BTC").map((h) => h.event_id);
    // Row 3 (settled) is excluded by the default active status; rows 4/5 have no BTC.
    expect(ids).toEqual([2, 1]);
  });

  it("ranks active-first, then by descending volume, then id", () => {
    const hits = searchSample(rows, "btc", "all");
    expect(hits.map((h) => h.event_id)).toEqual([2, 1, 3]);
    // The settled row sinks below all active ones despite its 5000 volume.
    expect(hits[hits.length - 1]).toMatchObject({ event_id: 3, active: false, outcome: 1 });
  });

  it("scopes by status", () => {
    expect(searchSample(rows, "btc", "settled").map((h) => h.event_id)).toEqual([3]);
    expect(searchSample(rows, "btc", "active").map((h) => h.event_id)).toEqual([2, 1]);
  });

  it("maps a sample row to the API hit shape", () => {
    const [hit] = searchSample(rows, "flip", "active");
    expect(hit).toEqual<SearchHit>({
      event_id: 4,
      question: "Will ETH flip to number one?",
      category: "crypto",
      source: "polymarket",
      yes_price: 0.8,
      outcome: null,
      active: true,
    });
  });

  it("honours the limit", () => {
    expect(searchSample(rows, "btc", "all", 2).map((h) => h.event_id)).toEqual([2, 1]);
  });

  it("returns [] for a too-short query, non-positive limit, or non-array input", () => {
    expect(searchSample(rows, "b", "all")).toEqual([]);
    expect(searchSample(rows, "", "all")).toEqual([]);
    expect(searchSample(rows, "btc", "all", 0)).toEqual([]);
    expect(searchSample(undefined as unknown as MarketItem[], "btc")).toEqual([]);
  });

  it("does not mutate its input", () => {
    const snapshot = rows.map((r) => r.id);
    searchSample(rows, "btc", "all");
    expect(rows.map((r) => r.id)).toEqual(snapshot);
  });
});

describe("searchMarkets", () => {
  function fakeFetch(status: number, body: unknown) {
    const calls: string[] = [];
    const impl = (async (url: unknown) => {
      calls.push(String(url));
      return { ok: status >= 200 && status < 300, status, json: async () => body };
    }) as unknown as typeof fetch;
    return { impl, calls };
  }

  it("sends q and status and returns the items envelope", async () => {
    const { impl, calls } = fakeFetch(200, {
      query: "btc",
      items: [{ event_id: 7 } as SearchHit],
    });
    const hits = await searchMarkets("btc", "settled", { fetchImpl: impl });
    expect(hits.map((h) => h.event_id)).toEqual([7]);
    expect(calls[0]).toContain("/api/market-search?");
    expect(calls[0]).toContain("q=btc");
    expect(calls[0]).toContain("status=settled");
  });

  it("tolerates a bare-list body", async () => {
    const { impl } = fakeFetch(200, [{ event_id: 9 } as SearchHit]);
    expect((await searchMarkets("x", "all", { fetchImpl: impl })).map((h) => h.event_id)).toEqual([9]);
  });

  it("throws a readable error on a non-2xx response", async () => {
    const { impl } = fakeFetch(503, {});
    await expect(searchMarkets("x", "all", { fetchImpl: impl })).rejects.toThrow(
      /market search failed \(503\)/,
    );
  });
});
