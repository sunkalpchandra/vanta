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
import type { AgentCalibrationBin } from "@/lib/types";

const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const SERIES = "#3987e5";

export function AgentCalibrationChart({ bins }: { bins: AgentCalibrationBin[] }) {
  const data = bins.map((b) => ({
    mid: Math.round(b.mid * 100),
    perfect: Math.round(b.mid * 100),
    observed: b.observed_rate == null ? null : Math.round(b.observed_rate * 100),
  }));
  if (!data.some((d) => d.observed != null)) return null;
  return (
    <div className="h-52 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="mid"
            type="number"
            domain={[0, 100]}
            ticks={[0, 50, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 50, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value: number, name: string) => [`${value}%`, name]}
            labelFormatter={(label: number) => `predicted ≈ ${label}%`}
            contentStyle={{ background: "#0f131b", border: "1px solid #1e2632", borderRadius: 8, fontSize: 12 }}
          />
          <Line dataKey="perfect" stroke={INK_MUTED} strokeDasharray="4 4" strokeWidth={1} dot={false} />
          <Line
            dataKey="observed"
            stroke={SERIES}
            strokeWidth={2}
            connectNulls
            dot={{ r: 3, fill: SERIES, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
