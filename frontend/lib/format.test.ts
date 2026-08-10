import { describe, expect, it } from "vitest";
import { pct, shortDate, signedPct } from "./format";

describe("pct", () => {
  it("rounds to whole percent", () => {
    expect(pct(0.724)).toBe("72%");
    expect(pct(0.725)).toBe("73%");
    expect(pct(0)).toBe("0%");
    expect(pct(1)).toBe("100%");
  });
});

describe("signedPct", () => {
  it("carries the sign", () => {
    expect(signedPct(0.05)).toBe("+5%");
    expect(signedPct(-0.05)).toBe("-5%");
    expect(signedPct(0)).toBe("+0%");
  });
});

describe("shortDate", () => {
  it("treats offset-less API timestamps as UTC (regression)", () => {
    // 03:21 UTC on Aug 10 is still Aug 9 in any US timezone; the raw string
    // must not be parsed as local wall-clock time.
    const withZ = shortDate("2026-08-10T03:21:58Z");
    const bare = shortDate("2026-08-10T03:21:58");
    expect(bare).toBe(withZ);
  });

  it("respects explicit offsets", () => {
    expect(shortDate("2026-08-10T03:21:58+00:00")).toBe(shortDate("2026-08-10T03:21:58Z"));
  });
});
