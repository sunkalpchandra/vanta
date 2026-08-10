import { describe, expect, it } from "vitest";
import { buildPriceSeries } from "./marketDetail";

describe("buildPriceSeries", () => {
  it("maps yes_price 0..1 to 0..100 rows sorted oldest→newest", () => {
    const rows = buildPriceSeries([
      { timestamp: "2026-08-02T10:00:00Z", yes_price: 0.62 },
      { timestamp: "2026-08-01T09:00:00Z", yes_price: 0.4 },
    ]);
    expect(rows).toEqual([
      { t: "2026-08-01T09:00:00Z", price: 40 },
      { t: "2026-08-02T10:00:00Z", price: 62 },
    ]);
  });

  it("rounds to one decimal and clamps to 0..100", () => {
    const ts = "2026-08-01T00:00:00Z";
    expect(buildPriceSeries([{ timestamp: ts, yes_price: 0.12345 }])[0].price).toBe(12.3);
    expect(buildPriceSeries([{ timestamp: ts, yes_price: 1.4 }])[0].price).toBe(100);
    expect(buildPriceSeries([{ timestamp: ts, yes_price: -0.2 }])[0].price).toBe(0);
  });

  it("keeps a 0.0 price — a real observation, not a falsy drop", () => {
    const rows = buildPriceSeries([{ timestamp: "2026-08-01T00:00:00Z", yes_price: 0 }]);
    expect(rows).toEqual([{ t: "2026-08-01T00:00:00Z", price: 0 }]);
  });

  it("dedupes exact-duplicate timestamps, last write wins", () => {
    const rows = buildPriceSeries([
      { timestamp: "2026-08-01T00:00:00Z", yes_price: 0.4 },
      { timestamp: "2026-08-01T00:00:00Z", yes_price: 0.45 },
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].price).toBe(45);
  });

  it("drops points with no usable timestamp or price", () => {
    const rows = buildPriceSeries([
      { yes_price: 0.5 }, // no timestamp
      { timestamp: "2026-08-01T00:00:00Z" }, // no price field
      { timestamp: "2026-08-02T00:00:00Z", yes_price: null }, // null price
      { timestamp: "2026-08-03T00:00:00Z", yes_price: 0.5 }, // kept
    ]);
    expect(rows).toEqual([{ t: "2026-08-03T00:00:00Z", price: 50 }]);
  });

  it("accepts probability / price / p field variants and unix `t` seconds", () => {
    const ts = "2026-08-01T00:00:00Z";
    expect(buildPriceSeries([{ timestamp: ts, probability: 0.3 }])[0].price).toBe(30);
    expect(buildPriceSeries([{ timestamp: ts, price: 0.7 }])[0].price).toBe(70);
    const unix = buildPriceSeries([{ t: 1_754_006_400, p: 0.55 }]);
    expect(unix).toHaveLength(1);
    expect(unix[0].price).toBe(55);
    expect(unix[0].t).toBe(new Date(1_754_006_400 * 1000).toISOString());
  });

  it("returns [] for null / undefined / empty input", () => {
    expect(buildPriceSeries(null)).toEqual([]);
    expect(buildPriceSeries(undefined)).toEqual([]);
    expect(buildPriceSeries([])).toEqual([]);
  });
});
