import { describe, expect, it } from "vitest";
import { sparklinePath } from "./sparkline";

describe("sparklinePath", () => {
  it("returns null for degenerate series", () => {
    expect(sparklinePath([], 96, 28)).toBeNull();
    expect(sparklinePath([0.5], 96, 28)).toBeNull();
  });

  it("spans the padded width and inverts y (higher probability = higher pixel)", () => {
    const geometry = sparklinePath([0, 1], 100, 30, 2);
    expect(geometry).not.toBeNull();
    expect(geometry!.path.startsWith("M2.0,28.0")).toBe(true); // p=0 at bottom
    expect(geometry!.endX).toBe(98);
    expect(geometry!.endY).toBe(2); // p=1 at top
  });

  it("emits one segment per point", () => {
    const geometry = sparklinePath([0.2, 0.4, 0.6, 0.8], 96, 28)!;
    expect(geometry.path.match(/[ML]/g)).toHaveLength(4);
    expect(geometry.path.match(/M/g)).toHaveLength(1);
  });

  it("keeps every coordinate inside the box", () => {
    const geometry = sparklinePath([0, 0.5, 1, 0.25], 96, 28)!;
    for (const [, x, y] of geometry.path.matchAll(/[ML]([\d.]+),([\d.]+)/g)) {
      expect(Number(x)).toBeGreaterThanOrEqual(0);
      expect(Number(x)).toBeLessThanOrEqual(96);
      expect(Number(y)).toBeGreaterThanOrEqual(0);
      expect(Number(y)).toBeLessThanOrEqual(28);
    }
  });
});
