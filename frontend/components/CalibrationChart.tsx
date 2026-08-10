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
import type { CalibrationBin } from "@/lib/types";

const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const VANTA = "#3987e5";
const MARKET = "#d95926";

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number | null; color: string }[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.name !== "perfect" && p.value != null);
  if (!rows.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="micro-label">predicted ≈ {label}%</div>
      {rows.map((entry) => (
        <div key={entry.name} className="mt-1 flex items-center gap-2">
          <span className="h-2 w-2 rounded-sm" style={{ background: entry.color }} />
          <span className="text-ink-2">{entry.name} observed</span>
          <span className="num ml-auto pl-3 font-bold text-ink">{entry.value}%</span>
        </div>
      ))}
    </div>
  );
}

export function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const data = bins.map((b) => ({
    mid: Math.round(b.mid * 100),
    perfect: Math.round(b.mid * 100),
    vanta: b.vanta_observed_rate == null ? null : +(b.vanta_observed_rate * 100).toFixed(0),
    market: b.market_observed_rate == null ? null : +(b.market_observed_rate * 100).toFixed(0),
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: -16 }}>
          <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="mid"
            type="number"
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
            label={{ value: "predicted", position: "insideBottom", offset: -2, fill: INK_MUTED, fontSize: 11 }}
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
            formatter={(value: string) =>
              value === "perfect" ? (
                <span style={{ color: INK_MUTED, fontSize: 12 }}>perfect calibration</span>
              ) : (
                <span style={{ color: "#9aa4b2", fontSize: 12 }}>{value}</span>
              )
            }
            iconSize={10}
          />
          <Line
            dataKey="perfect"
            name="perfect"
            stroke={INK_MUTED}
            strokeDasharray="4 4"
            strokeWidth={1}
            dot={false}
            activeDot={false}
          />
          <Line
            dataKey="vanta"
            name="vanta"
            stroke={VANTA}
            strokeWidth={2}
            connectNulls
            dot={{ r: 3, fill: VANTA, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: VANTA, stroke: "#0f131b", strokeWidth: 2 }}
          />
          <Line
            dataKey="market"
            name="market"
            stroke={MARKET}
            strokeWidth={2}
            connectNulls
            dot={{ r: 3, fill: MARKET, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: MARKET, stroke: "#0f131b", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
