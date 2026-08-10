import { describe, expect, it } from "vitest";
import { filterFeed } from "./feedFilter";
import type { FeedCard } from "./types";

function card(overrides: Partial<FeedCard>): FeedCard {
  return {
    question_id: 1,
    question: "Will X happen?",
    category: "technology",
    market_probability: 0.5,
    vanta_probability: 0.6,
    confidence: 5,
    edge: 0.1,
    horizon_days: 90,
    headline: "",
    ...overrides,
  };
}

const CARDS = [
  card({ question_id: 1, question: "Will the Fed cut rates?", category: "finance", edge: 0.05, confidence: 8 }),
  card({ question_id: 2, question: "Will GPT-6 ship?", category: "technology", edge: -0.2, confidence: 3 }),
  card({ question_id: 3, question: "Will Bitcoin reach $150k?", category: "crypto", edge: 0.1, confidence: 6 }),
];

describe("filterFeed", () => {
  it("filters by category", () => {
    expect(filterFeed(CARDS, "finance", "", "edge").map((c) => c.question_id)).toEqual([1]);
  });

  it("search is case-insensitive and trims", () => {
    expect(filterFeed(CARDS, "all", "  bitcoin ", "edge").map((c) => c.question_id)).toEqual([3]);
  });

  it("sorts by absolute edge", () => {
    expect(filterFeed(CARDS, "all", "", "edge").map((c) => c.question_id)).toEqual([2, 3, 1]);
  });

  it("sorts by confidence", () => {
    expect(filterFeed(CARDS, "all", "", "confidence").map((c) => c.question_id)).toEqual([1, 3, 2]);
  });

  it("does not mutate the input array", () => {
    const ids = CARDS.map((c) => c.question_id);
    filterFeed(CARDS, "all", "", "edge");
    expect(CARDS.map((c) => c.question_id)).toEqual(ids);
  });
});
