"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { buildEquitySeries, type EquityPoint, type EquityRow } from "@/lib/equity";
import { shortDate } from "@/lib/format";
import { formatStamp } from "@/lib/marketDetail";
import { authHeaders, clearTraderKey, fmtCredits, getTraderKey } from "@/lib/trader";

// Shared dark-theme palette (matches MarketPriceChart / ProbabilityChart).
const INK_MUTED = "#5c6675";
const GRID = "#1e2632";
const ACCENT = "#3987e5"; // the product accent — cash line/fill

const DISCLAIMER = "play money · paper trading · real market prices";
const CAPTION = "cash flow from trades · excludes settlement payouts";

// Compact ⓥ axis ticks: "ⓥ9,960" (no cents — the axis just needs the level).
const axisTick = (v: number) => `ⓥ${Math.round(v).toLocaleString("en-US")}`;

function EquityTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value?: number | null; payload?: EquityRow }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0];
  if (row.value == null || !row.payload) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-xl">
      <div className="text-muted">{formatStamp(row.payload.t)}</div>
      <div className="mt-1 flex items-center gap-2">
        <span className="h-2 w-2 rounded-sm" style={{ background: ACCENT }} />
        <span className="text-ink-2">cash</span>
        <span className="num ml-auto pl-3 font-bold text-ink">{fmtCredits(row.value)}</span>
      </div>
    </div>
  );
}

/** Single-series ⓥ-cash area over time. A sparse series (<3 points) renders
 * with dots so a one- or two-point history is still visible. */
function CashArea({ rows }: { rows: EquityRow[] }) {
  const sparse = rows.length < 3;
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="vanta-equity-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
              <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
            </linearGradient>
          </defs>
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
            domain={["auto", "auto"]}
            tickFormatter={axisTick}
            tick={{ fill: INK_MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          <Tooltip content={<EquityTooltip />} cursor={{ stroke: INK_MUTED, strokeDasharray: "3 3" }} />
          <Area
            type="monotone"
            dataKey="cash"
            name="cash"
            stroke={ACCENT}
            strokeWidth={2}
            fill="url(#vanta-equity-fill)"
            connectNulls
            dot={sparse ? { r: 3, fill: ACCENT, strokeWidth: 0 } : false}
            activeDot={{ r: 4, fill: ACCENT, stroke: "#0f131b", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="card p-4">
      <div className="micro-label px-1">equity over time</div>
      {children}
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <Frame>
      <div className="px-1 py-10 text-center text-sm text-muted">{children}</div>
      <div className="micro-label px-1">{DISCLAIMER}</div>
    </Frame>
  );
}

function Ready({ rows }: { rows: EquityRow[] }) {
  if (rows.length === 0) return <Empty>No trades yet — your cash curve starts once you buy or sell.</Empty>;
  return (
    <Frame>
      <CashArea rows={rows} />
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 px-1">
        <span className="micro-label">{CAPTION}</span>
        <span className="micro-label">{DISCLAIMER}</span>
      </div>
    </Frame>
  );
}

type ViewState = "loading" | "nokey" | "rejected" | "error" | "ready";

/** Live variant: fetches the caller's cash-flow series from
 * /api/portfolio/equity with the trading identity, mirroring PortfolioView's
 * key/rejected/error states. */
function LiveEquityChart() {
  const [state, setState] = useState<ViewState>("loading");
  const [rows, setRows] = useState<EquityRow[]>([]);

  const load = useCallback(async () => {
    if (getTraderKey() === null) {
      setState("nokey");
      return;
    }
    setState("loading");
    try {
      const res = await fetch(`${API_URL}/api/portfolio/equity`, { headers: authHeaders() });
      if (res.status === 401) {
        setState("rejected");
        return;
      }
      if (!res.ok) throw new Error(String(res.status));
      const body = (await res.json()) as { points?: EquityPoint[] };
      setRows(buildEquitySeries(body.points));
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    if (!IS_STATIC) load();
  }, [load]);

  if (IS_STATIC) {
    return (
      <Empty>
        The static demo has no trading backend, so there is no cash curve to show. Run the backend
        locally to trade with ⓥ10,000 play credits.
      </Empty>
    );
  }
  if (state === "loading") return <Empty>Loading equity…</Empty>;
  if (state === "nokey") return <Empty>No trader identity yet — open a market to start trading.</Empty>;
  if (state === "rejected") {
    return (
      <Frame>
        <div className="px-1 py-8 text-center text-sm text-ink-2">
          The trading key stored in this browser was rejected by the backend.
          <div className="mt-3">
            <button
              onClick={() => {
                clearTraderKey();
                setState("nokey");
              }}
              className="rounded-lg border border-line px-4 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
            >
              Forget key &amp; start over
            </button>
          </div>
        </div>
      </Frame>
    );
  }
  if (state === "error") return <Empty>Couldn&apos;t load your equity — is the backend running?</Empty>;
  return <Ready rows={rows} />;
}

/**
 * Play-money cash-over-time chart. Pass `points` to render a supplied series
 * (e.g. a baked snapshot); omit it to fetch the caller's live series from
 * /api/portfolio/equity with the stored trading identity.
 *
 * The series is *cash flow from trades*, not mark-to-market equity — settlement
 * payouts credit the balance directly and are excluded (see lib/equity + the
 * router docstring). Labeled as such so it can't be mistaken for balance.
 */
export function EquityChart({ points }: { points?: EquityPoint[] }) {
  if (points !== undefined) return <Ready rows={buildEquitySeries(points)} />;
  return <LiveEquityChart />;
}
