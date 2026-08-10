export const pct = (p: number) => `${Math.round(p * 100)}%`;

export const signedPct = (p: number) => `${p >= 0 ? "+" : ""}${Math.round(p * 100)}%`;

// Treat offset-less API timestamps as UTC: JS parses "2026-08-10T03:21:58" as
// LOCAL time, which shifts chart dates by the viewer's UTC offset.
const asUtc = (iso: string) => (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);

export const shortDate = (iso: string) =>
  new Date(asUtc(iso)).toLocaleDateString("en-US", { month: "short", day: "numeric" });
