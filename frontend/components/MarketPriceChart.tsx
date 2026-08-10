"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { shortDate } from "@/lib/format";
import { formatStamp, type PriceRow } from "@/lib/marketDetail";

// Shared with ProbabilityChart's dark-theme palette.
const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const ACCENT = "#3987e5"; // YES-price line — the product accent

function PriceTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value?: number | null; payload?: PriceRow }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0];
  if (row.value == null || !row.payload) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="text-muted">{formatStamp(row.payload.t)}</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="h-2 w-2 rounded-sm" style={{ background: ACCENT }} />
        <span className="text-ink-2">YES</span>
        <span className="num ml-auto pl-3 font-bold text-ink">{row.value.toFixed(1)}%</span>
      </div>
    </div>
  );
}

/** Single-series YES-price line over time (0-100%). A sparse series (<3 points)
 * renders with dots so a one- or two-tick history is still visible — a bare
 * line through one point is a zero-length, invisible path. */
export function MarketPriceChart({ rows }: { rows: PriceRow[] }) {
  const sparse = rows.length < 3;
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="t"
            tickFormatter={shortDate}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
            minTickGap={48}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<PriceTooltip />} cursor={{ stroke: INK_MUTED, strokeDasharray: "3 3" }} />
          <Line
            type="monotone"
            dataKey="price"
            name="YES"
            stroke={ACCENT}
            strokeWidth={2}
            connectNulls
            dot={sparse ? { r: 3, fill: ACCENT, strokeWidth: 0 } : false}
            activeDot={{ r: 4, fill: ACCENT, stroke: "#0f131b", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
