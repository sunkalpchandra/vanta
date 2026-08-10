"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { pct, signedPct } from "@/lib/format";

export interface MarketForecastData {
  probability: number;
  market_probability: number;
  confidence: number;
  edge: number;
  direction: "agree" | "disagree" | "neutral";
  reasoning: string;
  risk_factors: string[];
  agent_reports: { agent: string; stance: string; probability: number | null; argument: string }[];
}

const STANCE_TONE: Record<string, string> = {
  bull: "text-pos",
  bear: "text-neg",
  neutral: "text-ink-2",
};

/** vanta's own forecast on a market event — its probability vs the venue
 * price, the edge, and the agent debate behind it. Deterministic quant
 * numbers; prose is optional LLM narration. Fetched live; in static mode it
 * renders a baked forecast when the detail page supplies one. */
export function MarketForecast({
  eventId,
  initial,
}: {
  eventId: number;
  initial?: MarketForecastData | null;
}) {
  const [data, setData] = useState<MarketForecastData | null>(initial ?? null);
  const [state, setState] = useState<"idle" | "loading" | "error">(
    initial ? "idle" : IS_STATIC ? "idle" : "loading",
  );

  useEffect(() => {
    if (initial || IS_STATIC) return;
    let cancelled = false;
    setState("loading");
    fetch(`${API_URL}/api/markets/${eventId}/forecast`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: MarketForecastData) => !cancelled && (setData(d), setState("idle")))
      .catch(() => !cancelled && setState("error"));
    return () => {
      cancelled = true;
    };
  }, [eventId, initial]);

  if (!data) {
    return (
      <div className="card p-5 text-sm text-muted">
        {state === "loading"
          ? "Running the agent pipeline…"
          : state === "error"
            ? "Couldn't load vanta's forecast — is the backend running?"
            : "vanta's forecast needs the live backend."}
      </div>
    );
  }

  const agrees = data.direction === "agree";
  const tone = data.direction === "neutral" ? "text-ink-2" : agrees ? "text-pos" : "text-neg";
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="micro-label">vanta&apos;s take</span>
        <span className={`micro-label ${tone}`}>
          {data.direction === "neutral"
            ? "in line with the market"
            : `${agrees ? "agrees" : "disagrees"} — edge ${signedPct(data.edge)}`}
        </span>
        <span className="micro-label ml-auto">confidence {data.confidence.toFixed(1)}/10</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-4">
        <div>
          <div className="micro-label">market</div>
          <div className="num mt-1 text-2xl font-bold text-ink-2">{pct(data.market_probability)}</div>
        </div>
        <div>
          <div className="micro-label">vanta</div>
          <div className="num mt-1 text-2xl font-bold text-accent">{pct(data.probability)}</div>
        </div>
      </div>
      {data.reasoning && <p className="mt-3 text-sm leading-relaxed text-ink-2">{data.reasoning}</p>}
      <details className="mt-4">
        <summary className="micro-label cursor-pointer select-none hover:text-ink">
          agent debate ({data.agent_reports.length})
        </summary>
        <ul className="mt-3 space-y-2">
          {data.agent_reports.map((r) => (
            <li key={r.agent} className="text-sm text-ink-2">
              <span className="micro-label">{r.agent}</span>{" "}
              <span className={`micro-label ${STANCE_TONE[r.stance] ?? "text-ink-2"}`}>{r.stance}</span>
              <span className="ml-2">{r.argument}</span>
            </li>
          ))}
        </ul>
      </details>
      <p className="micro-label mt-3 text-muted">
        deterministic quant forecast · play money · not investment advice
      </p>
    </div>
  );
}
