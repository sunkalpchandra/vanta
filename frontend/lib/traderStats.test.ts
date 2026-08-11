import { describe, expect, it } from "vitest";
import { formatWinRate, pnlTone } from "./traderStats";

describe("formatWinRate", () => {
  it("renders a 0..1 fraction as a whole percent", () => {
    expect(formatWinRate(0.63)).toBe("63%");
    expect(formatWinRate(1)).toBe("100%");
    expect(formatWinRate(0)).toBe("0%");
  });

  it("rounds to the nearest percent", () => {
    expect(formatWinRate(0.666)).toBe("67%");
    expect(formatWinRate(0.5)).toBe("50%");
  });

  it("dashes an undefined rate", () => {
    expect(formatWinRate(null)).toBe("—");
    expect(formatWinRate(Number.NaN)).toBe("—");
  });
});

describe("pnlTone", () => {
  it("greens gains, reds losses, flat for exactly zero", () => {
    expect(pnlTone(12.5)).toBe("pos");
    expect(pnlTone(0.01)).toBe("pos");
    expect(pnlTone(-0.01)).toBe("neg");
    expect(pnlTone(-99)).toBe("neg");
    expect(pnlTone(0)).toBe("flat");
    expect(pnlTone(-0)).toBe("flat");
  });
});
