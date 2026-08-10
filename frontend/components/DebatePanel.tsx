"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { AgentReportOut } from "@/lib/types";
import { pct } from "@/lib/format";
import { StanceChip } from "./Badges";

const AGENT_META: Record<string, { title: string; blurb: string }> = {
  research: { title: "Research Agent", blurb: "qualitative evidence" },
  quant: { title: "Quant Agent", blurb: "historical analogs · monte carlo" },
  market: { title: "Market Agent", blurb: "prediction-market consensus" },
  sentiment: { title: "Sentiment Agent", blurb: "public mood & momentum" },
  historian: { title: "Historian Agent", blurb: "base rates & horizon" },
  skeptic: { title: "Skeptic Agent", blurb: "attacks the consensus" },
  synthesis: { title: "Synthesis Agent", blurb: "final bayesian pool" },
};

export function DebatePanel({ reports }: { reports: AgentReportOut[] }) {
  const reduceMotion = useReducedMotion();
  return (
    <div className="space-y-3">
      {reports.map((report, i) => {
        const meta = AGENT_META[report.agent] ?? { title: report.agent, blurb: "" };
        const isSynthesis = report.agent === "synthesis";
        return (
          <motion.div
            key={report.agent}
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.3, delay: i * 0.05 }}
            className={`card p-4 ${isSynthesis ? "border-accent/40" : ""}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-sm font-semibold ${isSynthesis ? "text-accent" : "text-ink"}`}>
                {meta.title}
              </span>
              <span className="micro-label">{meta.blurb}</span>
              <div className="ml-auto flex items-center gap-2">
                {report.probability != null && (
                  <span className="num text-sm font-bold text-ink">{pct(report.probability)}</span>
                )}
                <StanceChip stance={report.stance} />
              </div>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{report.argument}</p>
            <DetailChips details={report.details} />
          </motion.div>
        );
      })}
    </div>
  );
}

/** Structured highlights from each agent's report details. */
function DetailChips({ details }: { details: Record<string, unknown> }) {
  const chips: string[] = [];
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  const ciLow = num(details.ci_low);
  const ciHigh = num(details.ci_high);
  if (ciLow != null && ciHigh != null) {
    chips.push(`90% CI ${Math.round(ciLow * 100)}–${Math.round(ciHigh * 100)}%`);
  }
  const n = num(details.n_analogs);
  if (n) chips.push(`${n} analogs`);
  const share = num(details.positive_share);
  if (share != null) chips.push(`${Math.round(share * 100)}% positive`);
  if (typeof details.momentum === "string" && details.momentum !== "flat") {
    chips.push(`momentum ${details.momentum}`);
  }
  const base = num(details.base_rate);
  if (base != null) chips.push(`base rate ${Math.round(base * 100)}%`);
  const haircut = num(details.confidence_haircut);
  if (haircut) chips.push(`confidence −${haircut.toFixed(1)}`);
  if (!chips.length) return null;
  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <span key={chip} className="num rounded border border-line px-1.5 py-0.5 text-[11px] text-muted">
          {chip}
        </span>
      ))}
    </div>
  );
}
