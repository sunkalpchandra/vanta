"use client";

import { useMemo, useState } from "react";
import type { FeedCard } from "@/lib/types";
import { FeedCardItem } from "./FeedCardItem";

export function FeedExplorer({ cards }: { cards: FeedCard[] }) {
  const [category, setCategory] = useState<string>("all");
  const categories = useMemo(
    () => ["all", ...Array.from(new Set(cards.map((c) => c.category))).sort()],
    [cards],
  );
  const visible = category === "all" ? cards : cards.filter((c) => c.category === category);

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Filter by category">
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
      {visible.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No live questions in this category.</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {visible.map((card, i) => (
            <FeedCardItem key={card.question_id} card={card} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
