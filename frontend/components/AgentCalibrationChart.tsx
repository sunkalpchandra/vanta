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

function CalibrationTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number | null }[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  const observed = payload.find((entry) => entry.name === "observed");
  if (!observed || observed.value == null) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="micro-label">predicted ≈ {label}%</div>
      <div className="num mt-0.5 font-bold text-ink">observed {observed.value}%</div>
    </div>
  );
}

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
            content={<CalibrationTooltip />}
            cursor={{ stroke: INK_MUTED, strokeDasharray: "3 3" }}
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
