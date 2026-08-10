// Pure feed filtering/sorting — extracted from FeedExplorer for testability.

import type { FeedCard } from "./types";

export type FeedSort = "edge" | "confidence";

export function filterFeed(
  cards: FeedCard[],
  category: string,
  query: string,
  sort: FeedSort,
): FeedCard[] {
  const q = query.trim().toLowerCase();
  return cards
    .filter(
      (c) =>
        (category === "all" || c.category === category) &&
        (!q || c.question.toLowerCase().includes(q)),
    )
    .sort((a, b) =>
      sort === "edge" ? Math.abs(b.edge) - Math.abs(a.edge) : b.confidence - a.confidence,
    );
}
