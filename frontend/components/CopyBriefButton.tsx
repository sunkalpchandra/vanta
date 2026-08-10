"use client";

import { useState } from "react";
import type { BriefItem } from "@/lib/types";
import { pct, signedPct } from "@/lib/format";

/** Copies the brief as share-ready plain text. */
export function CopyBriefButton({ brief }: { brief: BriefItem[] }) {
  const [copied, setCopied] = useState(false);
  if (!brief.length) return null;

  async function copy() {
    const lines = [
      "VANTA MORNING BRIEF — what the world is most wrong about",
      "",
      ...brief.map(
        (item) =>
          `${item.rank}. ${item.question}\n   market ${pct(item.market_probability)} · vanta ${pct(
            item.vanta_probability,
          )} (${signedPct(item.edge)})`,
      ),
      "",
      "https://sunkalpchandra.github.io/vanta/",
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable (permissions/http) — leave the button as-is
    }
  }

  return (
    <button
      onClick={copy}
      className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
    >
      {copied ? "Copied ✓" : "Copy as text"}
    </button>
  );
}
