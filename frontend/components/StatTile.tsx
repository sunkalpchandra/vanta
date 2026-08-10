import Link from "next/link";

export function StatTile({
  label,
  value,
  tone = "default",
  sub,
  href,
}: {
  label: string;
  value: string;
  tone?: "default" | "accent" | "pos" | "neg";
  sub?: string;
  href?: string;
}) {
  const toneClass = {
    default: "text-ink",
    accent: "text-accent",
    pos: "text-pos",
    neg: "text-neg",
  }[tone];
  const body = (
    <>
      <div className="micro-label">{label}</div>
      <div className={`num mt-1.5 text-3xl font-bold ${toneClass}`}>{value}</div>
      {sub ? <div className="mt-1 text-xs text-muted">{sub}</div> : null}
    </>
  );
  if (href) {
    return (
      <Link href={href} className="card card-hover block px-5 py-4">
        {body}
      </Link>
    );
  }
  return <div className="card px-5 py-4">{body}</div>;
}
