import { signedPct } from "@/lib/format";

export function CategoryBadge({ category }: { category: string }) {
  return (
    <span className="micro-label rounded border border-line bg-surface-2 px-2 py-0.5 !text-ink-2">
      {category}
    </span>
  );
}

export function EdgeBadge({ edge }: { edge: number }) {
  // Sign + arrow carry the direction; color reinforces it.
  const positive = edge >= 0;
  return (
    <span
      className={`num rounded px-2 py-0.5 text-xs font-bold ${
        positive ? "bg-pos/15 text-pos" : "bg-neg/15 text-neg"
      }`}
    >
      {positive ? "▲" : "▼"} {signedPct(edge)} vs market
    </span>
  );
}

export function StanceChip({ stance }: { stance: "bull" | "bear" | "neutral" }) {
  const cls = {
    bull: "bg-pos/15 text-pos",
    bear: "bg-neg/15 text-neg",
    neutral: "bg-surface-2 text-ink-2",
  }[stance];
  return (
    <span className={`num rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${cls}`}>
      {stance}
    </span>
  );
}
