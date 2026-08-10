import type { HistoryPoint, MarketPoint } from "./types";

export type MergedDay = { timestamp: string; vanta?: number; market?: number };

export const dayKey = (iso: string) => iso.slice(0, 10);

/** Merge the vanta and market series onto one day-keyed axis. Multiple points
 * on the same day collapse to the last one (series are already chronological);
 * probabilities become 0-100 percentages rounded to one decimal. */
export function mergeDaySeries(history: HistoryPoint[], marketHistory: MarketPoint[]): MergedDay[] {
  const byDay = new Map<string, MergedDay>();
  for (const point of history) {
    const key = dayKey(point.timestamp);
    byDay.set(key, {
      ...(byDay.get(key) ?? { timestamp: point.timestamp }),
      vanta: +(point.probability * 100).toFixed(1),
    });
  }
  for (const point of marketHistory) {
    const key = dayKey(point.timestamp);
    byDay.set(key, {
      ...(byDay.get(key) ?? { timestamp: point.timestamp }),
      market: +(point.probability * 100).toFixed(1),
    });
  }
  return Array.from(byDay.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

/** Map evidence arrival dates onto the merged axis's own bucket keys — on a
 * category axis a ReferenceLine x must equal an existing data point's key. */
export function evidenceTicksFor(evidenceDates: string[], data: MergedDay[]): string[] {
  const byDay = new Map(data.map((d) => [dayKey(d.timestamp), d.timestamp]));
  return Array.from(
    new Set(evidenceDates.map((iso) => byDay.get(dayKey(iso))).filter((t): t is string => Boolean(t))),
  );
}

/** A one-point line is a zero-length path — invisible without dots. */
export function needsDots(data: MergedDay[], series: "vanta" | "market"): boolean {
  return data.filter((d) => d[series] != null).length < 3;
}
