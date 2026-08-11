import { describe, expect, it } from "vitest";
import {
  categoryCounts,
  filterByCategory,
  MARKET_CATEGORY_SLUGS,
} from "./marketCategories";
import type { MarketItem } from "./trader";

function mkt(overrides: Partial<MarketItem>): MarketItem {
  return {
    id: 1,
    question: "Will X happen?",
    category: "technology",
    source: "polymarket",
    yes_price: 0.5,
    volume_usd: 1000,
    close_time: null,
    outcome: null,
    ...overrides,
  };
}

const ITEMS: MarketItem[] = [
  mkt({ id: 1, category: "technology" }),
  mkt({ id: 2, category: "finance" }),
  mkt({ id: 3, category: "technology" }),
  mkt({ id: 4, category: "other" }),
  mkt({ id: 5, category: "weather" }), // unrecognized → buckets to "other"
];

describe("MARKET_CATEGORY_SLUGS", () => {
  it("is the six curated categories plus 'other'", () => {
    expect(MARKET_CATEGORY_SLUGS).toEqual([
      "technology",
      "finance",
      "politics",
      "science",
      "sports",
      "crypto",
      "other",
    ]);
  });
});

describe("filterByCategory", () => {
  it("returns exactly the items in a known category", () => {
    expect(filterByCategory(ITEMS, "technology").map((m) => m.id)).toEqual([1, 3]);
    expect(filterByCategory(ITEMS, "finance").map((m) => m.id)).toEqual([2]);
  });

  it("buckets the literal 'other' and any unrecognized category under 'other'", () => {
    expect(filterByCategory(ITEMS, "other").map((m) => m.id)).toEqual([4, 5]);
  });

  it("returns [] for a known slug with no items", () => {
    expect(filterByCategory(ITEMS, "sports")).toEqual([]);
  });

  it("returns [] for a slug outside the known buckets", () => {
    expect(filterByCategory(ITEMS, "weather")).toEqual([]);
  });

  it("returns [] for an empty input", () => {
    expect(filterByCategory([], "technology")).toEqual([]);
  });

  it("does not mutate the input array", () => {
    const ids = ITEMS.map((m) => m.id);
    filterByCategory(ITEMS, "other");
    expect(ITEMS.map((m) => m.id)).toEqual(ids);
  });

  it("partitions every item into exactly one slug bucket", () => {
    const total = MARKET_CATEGORY_SLUGS.reduce(
      (sum, slug) => sum + filterByCategory(ITEMS, slug).length,
      0,
    );
    expect(total).toBe(ITEMS.length);
  });
});

describe("categoryCounts", () => {
  it("counts items per bucket, folding unknowns into 'other'", () => {
    expect(categoryCounts(ITEMS)).toEqual({ technology: 2, finance: 1, other: 2 });
  });

  it("is sparse — absent buckets are omitted, present ones sum to the total", () => {
    const counts = categoryCounts(ITEMS);
    expect(counts.sports).toBeUndefined();
    expect(Object.values(counts).reduce((a, b) => a + b, 0)).toBe(ITEMS.length);
  });

  it("returns an empty object for an empty input", () => {
    expect(categoryCounts([])).toEqual({});
  });

  it("agrees with filterByCategory for each slug", () => {
    const counts = categoryCounts(ITEMS);
    for (const slug of MARKET_CATEGORY_SLUGS) {
      expect(filterByCategory(ITEMS, slug).length).toBe(counts[slug] ?? 0);
    }
  });
});
