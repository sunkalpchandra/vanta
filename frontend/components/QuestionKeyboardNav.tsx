"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** "[" / "]" step to the previous / next question — terminal-style paging
 * through the corpus. Renders a small hint strip; no-ops while typing. */
export function QuestionKeyboardNav({ prevId, nextId }: { prevId?: number; nextId?: number }) {
  const router = useRouter();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.key === "[" && prevId != null) router.push(`/questions/${prevId}`);
      if (e.key === "]" && nextId != null) router.push(`/questions/${nextId}`);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, prevId, nextId]);

  if (prevId == null && nextId == null) return null;
  return (
    <span className="micro-label hidden sm:inline" aria-hidden>
      [ prev · next ]
    </span>
  );
}
