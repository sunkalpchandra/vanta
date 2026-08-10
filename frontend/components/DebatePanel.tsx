"use client";

import { motion } from "framer-motion";
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
  return (
    <div className="space-y-3">
      {reports.map((report, i) => {
        const meta = AGENT_META[report.agent] ?? { title: report.agent, blurb: "" };
        const isSynthesis = report.agent === "synthesis";
        return (
          <motion.div
            key={report.agent}
            initial={{ opacity: 0, y: 10 }}
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
          </motion.div>
        );
      })}
    </div>
  );
}
