"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { type FeedSort, filterFeed } from "@/lib/feedFilter";
import type { FeedCard } from "@/lib/types";
import { FeedCardItem } from "./FeedCardItem";

export function FeedExplorer({
  cards,
  sparklines,
}: {
  cards: FeedCard[];
  sparklines?: Record<string, number[]>;
}) {
  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<FeedSort>("edge");
  const [starredOnly, setStarredOnly] = useState(false);
  const [starredIds, setStarredIds] = useState<number[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);

  const refreshStars = () => import("@/lib/starred").then((m) => setStarredIds(m.getStarred()));
  useEffect(() => {
    refreshStars();
  }, [starredOnly]);

  // "/" focuses search from anywhere on the page (unless already typing).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing = target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const categories = useMemo(
    () => ["all", ...Array.from(new Set(cards.map((c) => c.category))).sort()],
    [cards],
  );
  const filtered = filterFeed(cards, category, query, sort);
  const visible = starredOnly ? filtered.filter((c) => starredIds.includes(c.question_id)) : filtered;

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
          <button
            onClick={() => setStarredOnly((v) => !v)}
            aria-pressed={starredOnly}
            className={`micro-label rounded-full border px-3 py-1.5 transition-colors ${
              starredOnly ? "border-accent !text-accent" : "border-line !text-ink-2 hover:border-accent/50"
            }`}
          >
            ★ starred
          </button>
        </div>
        <div className="ml-auto flex w-full items-center gap-2 sm:w-auto">
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as FeedSort)}
            aria-label="Sort feed"
            className="micro-label rounded-full border border-line bg-surface-2 px-3 py-1.5 !text-ink-2 outline-none focus:border-accent"
          >
            <option value="edge">by edge</option>
            <option value="confidence">by confidence</option>
          </select>
          <input
            ref={searchRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…  ( / )"
            aria-label="Search questions"
            className="w-full rounded-full border border-line bg-surface-2 px-4 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent sm:w-52"
          />
        </div>
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
              sparkline={sparklines?.[String(card.question_id)]}
              onStarChange={refreshStars}
            />
          ))}
        </div>
      )}
    </div>
  );
}
