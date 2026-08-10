"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LeaderboardRow } from "@/lib/types";

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
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="micro-label">{label}</div>
      {payload.map((entry) => (
        <div key={entry.name} className="mt-1 flex items-center gap-2">
          <span className="h-2 w-2 rounded-sm" style={{ background: entry.color }} />
          <span className="text-ink-2">{entry.name}</span>
          <span className="num ml-auto pl-3 font-bold text-ink">{entry.value}%</span>
        </div>
      ))}
    </div>
  );
}

export function AccuracyChart({ rows }: { rows: LeaderboardRow[] }) {
  const data = rows.map((r) => ({
    category: r.category,
    vanta: +(r.vanta_accuracy * 100).toFixed(1),
    market: +(r.market_accuracy * 100).toFixed(1),
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2}>
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="category"
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Legend
            formatter={(value: string) => (
              <span style={{ color: "#9aa4b2", fontSize: 12 }}>{value}</span>
            )}
            iconSize={10}
          />
          <Bar dataKey="vanta" name="vanta" fill={VANTA} radius={[4, 4, 0, 0]} maxBarSize={28} />
          <Bar dataKey="market" name="market" fill={MARKET} radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
