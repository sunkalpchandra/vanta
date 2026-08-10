import { sparklinePath } from "@/lib/sparkline";

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
  const geometry = sparklinePath(points, width, height);
  if (!geometry) return null;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={geometry.path} fill="none" stroke="#3987e5" strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={geometry.endX} cy={geometry.endY} r="2.5" fill="#3987e5" />
    </svg>
  );
}
