// Pure sparkline geometry — extracted so the math is unit-testable.

export interface SparklineGeometry {
  path: string;
  endX: number;
  endY: number;
}

export function sparklinePath(
  points: number[],
  width: number,
  height: number,
  pad = 2,
): SparklineGeometry | null {
  if (points.length < 2) return null;
  const xs = (i: number) => pad + (i / (points.length - 1)) * (width - pad * 2);
  const ys = (p: number) => pad + (1 - p) * (height - pad * 2);
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(p).toFixed(1)}`)
    .join(" ");
  return { path, endX: xs(points.length - 1), endY: ys(points[points.length - 1]) };
}
