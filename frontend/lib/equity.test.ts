import { describe, expect, it } from "vitest";
import { buildEquitySeries } from "./equity";

describe("buildEquitySeries", () => {
  it("sorts oldest→newest and preserves each cash level", () => {
    const rows = buildEquitySeries([
      { timestamp: "2026-08-02T10:00:00Z", cash: 9990 },
      { timestamp: "2026-08-01T09:00:00Z", cash: 9960 },
      { timestamp: "2026-08-01T00:00:00Z", cash: 10000 },
    ]);
    expect(rows).toEqual([
      { t: "2026-08-01T00:00:00Z", cash: 10000 },
      { t: "2026-08-01T09:00:00Z", cash: 9960 },
      { t: "2026-08-02T10:00:00Z", cash: 9990 },
    ]);
  });

  it("rounds cash to the cent", () => {
    const ts = "2026-08-01T00:00:00Z";
    expect(buildEquitySeries([{ timestamp: ts, cash: 9959.999 }])[0].cash).toBe(9960);
    expect(buildEquitySeries([{ timestamp: ts, cash: 9960.126 }])[0].cash).toBe(9960.13);
  });

  it("keeps cash of 0 and negative levels — real values, not falsy drops", () => {
    const rows = buildEquitySeries([
      { timestamp: "2026-08-01T00:00:00Z", cash: 0 },
      { timestamp: "2026-08-02T00:00:00Z", cash: -12.5 },
    ]);
    expect(rows).toEqual([
      { t: "2026-08-01T00:00:00Z", cash: 0 },
      { t: "2026-08-02T00:00:00Z", cash: -12.5 },
    ]);
  });

  it("drops points with no usable timestamp or a non-finite cash", () => {
    const rows = buildEquitySeries([
      { timestamp: "", cash: 100 }, // empty timestamp
      { timestamp: "2026-08-01T00:00:00Z", cash: Number.NaN }, // NaN cash
      // @ts-expect-error — cash missing entirely is tolerated and dropped
      { timestamp: "2026-08-02T00:00:00Z" },
      { timestamp: "2026-08-03T00:00:00Z", cash: 9960 }, // kept
    ]);
    expect(rows).toEqual([{ t: "2026-08-03T00:00:00Z", cash: 9960 }]);
  });

  it("keeps duplicate timestamps as distinct steps in input order (stable sort)", () => {
    const ts = "2026-08-01T00:00:00Z";
    const rows = buildEquitySeries([
      { timestamp: ts, cash: 9960 },
      { timestamp: ts, cash: 9990 },
    ]);
    expect(rows).toEqual([
      { t: ts, cash: 9960 },
      { t: ts, cash: 9990 },
    ]);
  });

  it("returns [] for null / undefined / empty input", () => {
    expect(buildEquitySeries(null)).toEqual([]);
    expect(buildEquitySeries(undefined)).toEqual([]);
    expect(buildEquitySeries([])).toEqual([]);
  });
});
