export function StatTile({
  label,
  value,
  tone = "default",
  sub,
}: {
  label: string;
  value: string;
  tone?: "default" | "accent" | "pos" | "neg";
  sub?: string;
}) {
  const toneClass = {
    default: "text-ink",
    accent: "text-accent",
    pos: "text-pos",
    neg: "text-neg",
  }[tone];
  return (
    <div className="card px-5 py-4">
      <div className="micro-label">{label}</div>
      <div className={`num mt-1.5 text-3xl font-bold ${toneClass}`}>{value}</div>
      {sub ? <div className="mt-1 text-xs text-muted">{sub}</div> : null}
    </div>
  );
}
