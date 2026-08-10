"use client";

import { useEffect, useState } from "react";
import { getStarred, toggleStar } from "@/lib/starred";

export function StarButton({ questionId, onChange }: { questionId: number; onChange?: () => void }) {
  const [starred, setStarred] = useState(false);
  useEffect(() => {
    setStarred(getStarred().includes(questionId));
  }, [questionId]);

  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setStarred(toggleStar(questionId).includes(questionId));
        onChange?.();
      }}
      aria-pressed={starred}
      aria-label={starred ? "Unstar question" : "Star question"}
      title={starred ? "Unstar" : "Star — saved in this browser"}
      className={`shrink-0 rounded px-1 text-base leading-none transition-colors ${
        starred ? "text-accent" : "text-muted hover:text-ink-2"
      }`}
    >
      {starred ? "★" : "☆"}
    </button>
  );
}
