"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint } from "@/lib/types";
import { pct, shortDate } from "@/lib/format";

const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const SERIES = "#3987e5";

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="text-muted">{label ? shortDate(label) : ""}</div>
      <div className="num mt-0.5 text-sm font-bold text-ink">{payload[0].value.toFixed(1)}%</div>
    </div>
  );
}

export function ProbabilityChart({
  history,
  marketProbability,
}: {
  history: HistoryPoint[];
  marketProbability: number;
}) {
  const data = history.map((h) => ({ ...h, probability: +(h.probability * 100).toFixed(1) }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 56, bottom: 0, left: -16 }}>
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
          <ReferenceLine
            y={marketProbability * 100}
            stroke={INK_MUTED}
            strokeDasharray="4 4"
            label={{
              value: `market ${pct(marketProbability)}`,
              position: "right",
              fill: INK_MUTED,
              fontSize: 11,
            }}
          />
          <Line
            type="monotone"
            dataKey="probability"
            stroke={SERIES}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: SERIES, stroke: "#0f131b", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
