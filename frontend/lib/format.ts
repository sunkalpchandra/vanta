export const pct = (p: number) => `${Math.round(p * 100)}%`;

export const signedPct = (p: number) => `${p >= 0 ? "+" : ""}${Math.round(p * 100)}%`;

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
