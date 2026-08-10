/** Tiny inline probability sparkline — server-renderable, no chart library.
 * Decorative reinforcement of the numbers beside it, so it's aria-hidden. */
export function Sparkline({
  points,
  width = 96,
  height = 28,
}: {
  points: number[]; // probabilities 0..1, oldest first
  width?: number;
  height?: number;
}) {
  if (points.length < 2) return null;
  const pad = 2;
  const xs = (i: number) => pad + (i / (points.length - 1)) * (width - pad * 2);
  const ys = (p: number) => pad + (1 - p) * (height - pad * 2);
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(p).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={path} fill="none" stroke="#3987e5" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={xs(points.length - 1)} cy={ys(last)} r="2.5" fill="#3987e5" />
    </svg>
  );
}
