"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint, MarketPoint } from "@/lib/types";
import { shortDate } from "@/lib/format";

const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const VANTA = "#3987e5"; // categorical slot 1
const MARKET = "#d95926"; // categorical slot 2

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number | null; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((entry) => entry.value != null);
  if (!rows.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="text-muted">{label ? shortDate(label) : ""}</div>
      {rows.map((entry) => (
        <div key={entry.name} className="mt-1 flex items-center gap-2">
          <span className="h-2 w-2 rounded-sm" style={{ background: entry.color }} />
          <span className="text-ink-2">{entry.name}</span>
          <span className="num ml-auto pl-3 font-bold text-ink">{entry.value?.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

/** vanta vs the market, over time — the product's core picture. Both series
 * merge onto one day-keyed axis; the market line is dashed so the pair stays
 * distinguishable without color. */
export function ProbabilityChart({
  history,
  marketHistory,
}: {
  history: HistoryPoint[];
  marketHistory: MarketPoint[];
}) {
  const byDay = new Map<string, { timestamp: string; vanta?: number; market?: number }>();
  const dayKey = (iso: string) => iso.slice(0, 10);
  for (const point of history) {
    const key = dayKey(point.timestamp);
    byDay.set(key, {
      ...(byDay.get(key) ?? { timestamp: point.timestamp }),
      vanta: +(point.probability * 100).toFixed(1),
    });
  }
  for (const point of marketHistory) {
    const key = dayKey(point.timestamp);
    byDay.set(key, {
      ...(byDay.get(key) ?? { timestamp: point.timestamp }),
      market: +(point.probability * 100).toFixed(1),
    });
  }
  const data = Array.from(byDay.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="timestamp"
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
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: INK_MUTED, strokeDasharray: "3 3" }} />
          <Legend
            formatter={(value: string) => <span style={{ color: "#9aa4b2", fontSize: 12 }}>{value}</span>}
            iconSize={10}
          />
          <Line
            type="monotone"
            dataKey="market"
            name="market"
            stroke={MARKET}
            strokeWidth={2}
            strokeDasharray="7 3"
            connectNulls
            dot={false}
            activeDot={{ r: 4, fill: MARKET, stroke: "#0f131b", strokeWidth: 2 }}
          />
          <Line
            type="monotone"
            dataKey="vanta"
            name="vanta"
            stroke={VANTA}
            strokeWidth={2}
            connectNulls
            dot={false}
            activeDot={{ r: 4, fill: VANTA, stroke: "#0f131b", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
