"use client";

import { useMemo, useState } from "react";
import type { FeedCard } from "@/lib/types";
import { FeedCardItem } from "./FeedCardItem";

export function FeedExplorer({
  cards,
  sparklines,
}: {
  cards: FeedCard[];
  sparklines?: Record<number, number[]>;
}) {
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const categories = useMemo(
    () => ["all", ...Array.from(new Set(cards.map((c) => c.category))).sort()],
    [cards],
  );
  const visible = cards.filter(
    (c) =>
      (category === "all" || c.category === category) &&
      (!query.trim() || c.question.toLowerCase().includes(query.trim().toLowerCase())),
  );

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Filter by category" className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              aria-pressed={category === c}
              className={`micro-label rounded-full border px-3 py-1.5 transition-colors ${
                category === c
                  ? "border-accent !text-accent"
                  : "border-line !text-ink-2 hover:border-accent/50"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search questions…"
          aria-label="Search questions"
          className="ml-auto w-full rounded-full border border-line bg-surface-2 px-4 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent sm:w-56"
        />
      </div>
      {visible.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No live questions match.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {visible.map((card, i) => (
            <FeedCardItem
              key={card.question_id}
              card={card}
              index={i}
              sparkline={sparklines?.[card.question_id]}
            />
          ))}
        </div>
      )}
    </div>
  );
}
