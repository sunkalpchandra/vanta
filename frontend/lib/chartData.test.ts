import { describe, expect, it } from "vitest";
import { evidenceTicksFor, mergeDaySeries, needsDots } from "./chartData";

const h = (ts: string, p: number) => ({ timestamp: ts, probability: p });

describe("mergeDaySeries", () => {
  it("buckets both series by day and sorts chronologically", () => {
    const merged = mergeDaySeries(
      [h("2026-08-02T10:00:00Z", 0.42), h("2026-08-01T09:00:00Z", 0.4)],
      [h("2026-08-01T12:00:00Z", 0.5)],
    );
    expect(merged.map((d) => d.timestamp.slice(0, 10))).toEqual(["2026-08-01", "2026-08-02"]);
    expect(merged[0]).toMatchObject({ vanta: 40, market: 50 });
    expect(merged[1].market).toBeUndefined();
  });

  it("same-day duplicates collapse to the last point", () => {
    const merged = mergeDaySeries([h("2026-08-01T09:00:00Z", 0.4), h("2026-08-01T18:00:00Z", 0.45)], []);
    expect(merged).toHaveLength(1);
    expect(merged[0].vanta).toBe(45);
  });

  it("rounds percentages to one decimal", () => {
    expect(mergeDaySeries([h("2026-08-01T00:00:00Z", 0.12345)], [])[0].vanta).toBe(12.3);
  });
});

describe("evidenceTicksFor", () => {
  const data = mergeDaySeries([h("2026-08-01T09:00:00Z", 0.4)], []);
  it("snaps evidence dates to existing bucket keys", () => {
    expect(evidenceTicksFor(["2026-08-01T23:00:00Z"], data)).toEqual(["2026-08-01T09:00:00Z"]);
  });
  it("drops dates with no matching bucket and dedupes", () => {
    expect(evidenceTicksFor(["2026-07-15T00:00:00Z"], data)).toEqual([]);
    expect(evidenceTicksFor(["2026-08-01T01:00:00Z", "2026-08-01T02:00:00Z"], data)).toHaveLength(1);
  });
});

describe("needsDots", () => {
  it("sparse series need dots; dense ones do not", () => {
    const sparse = mergeDaySeries([h("2026-08-01T00:00:00Z", 0.4)], []);
    expect(needsDots(sparse, "vanta")).toBe(true);
    expect(needsDots(sparse, "market")).toBe(true); // zero points is sparse too
    const dense = mergeDaySeries(
      [h("2026-08-01T00:00:00Z", 0.4), h("2026-08-02T00:00:00Z", 0.41), h("2026-08-03T00:00:00Z", 0.42)],
      [],
    );
    expect(needsDots(dense, "vanta")).toBe(false);
  });
});
