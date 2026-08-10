"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { API_URL } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { IS_STATIC } from "@/lib/config";
import { pct } from "@/lib/format";
import { createSseParser, type SseMessage } from "@/lib/sse";
import type { AgentReportOut, EvidenceOut } from "@/lib/types";
import { AgentStreamCard } from "./AgentStreamCard";
import { EdgeBadge } from "./Badges";
import { EvidenceList } from "./EvidenceList";

// Stream event payloads (mirrors the backend chat router's SSE contract).
interface ChatStatus {
  matched: boolean;
  question_id: number | null;
  question: string;
}

interface ChatForecast {
  question_id: number | null;
  market_probability: number;
  vanta_probability: number;
  confidence: number;
  risk_factors: string[];
  edge?: number;
}

export function ChatConsole() {
  if (IS_STATIC) {
    return <StaticChatConsole />;
  }
  return <LiveChatConsole />;
}

function LiveChatConsole() {
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState("technology");
  const [phase, setPhase] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [reports, setReports] = useState<AgentReportOut[]>([]);
  const [evidence, setEvidence] = useState<EvidenceOut[]>([]);
  const [forecast, setForecast] = useState<ChatForecast | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Abandon an in-flight stream if the user navigates away mid-deliberation.
  useEffect(() => () => abortRef.current?.abort(), []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase("streaming");
    setErrorMsg(null);
    setStatus(null);
    setReports([]);
    setEvidence([]);
    setForecast(null);

    // Set when the server pushes an `error` event; checked after the stream ends
    // so a clean close can't overwrite the failure with phase "done".
    let streamError: string | null = null;

    const handle = (msg: SseMessage) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        return; // never let one malformed frame kill the transcript
      }
      const d = parsed as Record<string, unknown>;
      switch (msg.event) {
        case "status":
          setStatus({
            matched: Boolean(d.matched),
            question_id: typeof d.question_id === "number" ? d.question_id : null,
            question: typeof d.question === "string" ? d.question : "",
          });
          break;
        case "agent_report":
          setReports((prev) => [...prev, d as unknown as AgentReportOut]);
          break;
        case "evidence":
          setEvidence(Array.isArray(parsed) ? (parsed as EvidenceOut[]) : []);
          break;
        case "forecast":
          setForecast(d as unknown as ChatForecast);
          break;
        case "error":
          streamError = typeof d.message === "string" ? d.message : "the agent stream failed";
          break;
      }
    };

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, category }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(detail || `the backend answered ${res.status}`);
      }
      if (!res.body) throw new Error("the backend sent an empty stream");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser();
      for (;;) {
        const { done, value } = await reader.read();
        // Final decode() flushes any buffered multi-byte character.
        const chunk = done ? decoder.decode() : decoder.decode(value, { stream: true });
        for (const msg of parser.feed(chunk)) handle(msg);
        if (done) break;
      }
      if (streamError) {
        setErrorMsg(streamError);
        setPhase("error");
      } else {
        setPhase("done");
      }
    } catch (err) {
      if (controller.signal.aborted) return; // superseded or unmounted, not a failure
      // A typed server `error` event is followed by an abrupt close that
      // throws in reader.read() — the server's message beats the generic one.
      setErrorMsg(
        streamError ?? (err instanceof Error && err.message ? err.message : "chat request failed"),
      );
      setPhase("error");
    }
  }

  const busy = phase === "streaming";
  return (
    <div>
      <form onSubmit={submit} className="card space-y-5 p-6">
        <ConsoleFields
          question={question}
          category={category}
          onQuestion={setQuestion}
          onCategory={setCategory}
          disabled={busy}
        />
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Agents deliberating…" : "Start deliberation"}
          </button>
          {phase === "error" && (
            <span className="text-xs text-neg">
              Chat failed — is the backend running?{errorMsg ? ` (${errorMsg})` : ""}
            </span>
          )}
        </div>
      </form>
      <Transcript
        status={status}
        reports={reports}
        evidence={evidence}
        forecast={forecast}
        streaming={busy}
      />
    </div>
  );
}

/** Question textarea + category select, shared by the live and static consoles. */
function ConsoleFields({
  question,
  category,
  onQuestion,
  onCategory,
  disabled,
}: {
  question: string;
  category: string;
  onQuestion?: (v: string) => void;
  onCategory?: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <>
      <div>
        <label htmlFor="chat-q" className="micro-label">
          Question
        </label>
        <textarea
          id="chat-q"
          required
          minLength={10}
          maxLength={500}
          rows={3}
          value={question}
          disabled={disabled}
          onChange={(e) => onQuestion?.(e.target.value)}
          placeholder='e.g. "Will the Fed cut rates before the December meeting?"'
          className="mt-2 w-full resize-none rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink outline-none placeholder:text-muted focus:border-accent disabled:opacity-50"
        />
      </div>
      <div>
        <label htmlFor="chat-cat" className="micro-label">
          Category
        </label>
        <select
          id="chat-cat"
          value={category}
          disabled={disabled}
          onChange={(e) => onCategory?.(e.target.value)}
          className="mt-2 block rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-accent disabled:opacity-50"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}

function Transcript({
  status,
  reports,
  evidence,
  forecast,
  streaming,
}: {
  status: ChatStatus | null;
  reports: AgentReportOut[];
  evidence: EvidenceOut[];
  forecast: ChatForecast | null;
  streaming: boolean;
}) {
  if (!status && !reports.length && !evidence.length && !forecast && !streaming) return null;
  return (
    <div className="mt-6 space-y-3">
      {status && <StatusLine status={status} />}
      {reports.map((report) => (
        <AgentStreamCard key={report.agent} report={report} />
      ))}
      {streaming && (
        <p className="micro-label animate-pulse" role="status">
          agents deliberating…
        </p>
      )}
      {evidence.length > 0 && (
        <div>
          <div className="micro-label mb-2 mt-5">evidence</div>
          <EvidenceList evidence={evidence} />
        </div>
      )}
      {forecast && <ForecastCard forecast={forecast} />}
    </div>
  );
}

function StatusLine({ status }: { status: ChatStatus }) {
  const label = status.matched ? "matched existing question" : "created new question";
  return (
    <p className="text-sm text-ink-2">
      <span className="micro-label">{label}</span>{" "}
      {status.question_id != null ? (
        <Link href={`/questions/${status.question_id}`} className="text-accent hover:underline">
          {status.question}
        </Link>
      ) : (
        <span className="text-ink">{status.question}</span>
      )}
    </p>
  );
}

function ForecastCard({ forecast }: { forecast: ChatForecast }) {
  const reduceMotion = useReducedMotion();
  const edge = forecast.edge ?? forecast.vanta_probability - forecast.market_probability;
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="card border-accent/40 p-5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="micro-label !text-accent">final forecast</span>
        <div className="ml-auto">
          <EdgeBadge edge={edge} />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 items-end gap-4">
        <div>
          <div className="micro-label">Market</div>
          <div className="num mt-1 text-2xl font-bold text-ink-2">
            {pct(forecast.market_probability)}
          </div>
        </div>
        <div>
          <div className="micro-label">vanta</div>
          <div className="num mt-1 text-2xl font-bold text-accent">
            {pct(forecast.vanta_probability)}
          </div>
        </div>
        <div className="micro-label justify-self-end">conf {forecast.confidence.toFixed(1)}/10</div>
      </div>
      {forecast.risk_factors.length > 0 && (
        <div className="mt-4">
          <div className="micro-label">risk factors</div>
          <ul className="mt-1.5 space-y-1">
            {forecast.risk_factors.map((risk) => (
              <li key={risk} className="text-xs leading-relaxed text-ink-2">
                · {risk}
              </li>
            ))}
          </ul>
        </div>
      )}
      {forecast.question_id != null && (
        <Link
          href={`/questions/${forecast.question_id}`}
          className="mt-4 inline-block text-sm text-accent hover:underline"
        >
          Full question page →
        </Link>
      )}
    </motion.div>
  );
}

// --- static demo -------------------------------------------------------------

// Hand-written sample so the static export shows what a deliberation looks
// like. Clearly labeled "example output" in the UI — never presented as live.
const EXAMPLE_TRANSCRIPT: {
  status: ChatStatus;
  reports: AgentReportOut[];
  evidence: EvidenceOut[];
  forecast: ChatForecast;
} = {
  status: {
    matched: false,
    question_id: null,
    question: "Will the Fed cut rates before the December meeting?",
  },
  reports: [
    {
      agent: "research",
      stance: "bull",
      probability: null,
      argument:
        "Recent FOMC minutes flag softening labor data, and two governors have publicly floated an earlier cut. Qualitative evidence leans toward easing.",
      details: {},
    },
    {
      agent: "quant",
      stance: "neutral",
      probability: 0.58,
      argument:
        "Six historical analogs with similar rate-path setups resolved YES 4 of 6 times; monte carlo over the horizon lands at 58% with a wide interval.",
      details: {},
    },
    {
      agent: "skeptic",
      stance: "bear",
      probability: 0.48,
      argument:
        "The consensus underweights sticky services inflation — the last three easing cycles started only after two consecutive soft CPI prints, which we do not have.",
      details: {},
    },
    {
      agent: "synthesis",
      stance: "bull",
      probability: 0.61,
      argument:
        "Pooling the panel with skeptic-adjusted weights lands modestly above the market. Evidence is directional but not decisive; confidence stays mid-range.",
      details: {},
    },
  ],
  evidence: [
    {
      source: "fixture:fomc-minutes",
      summary: "Minutes note 'increased downside risks to employment' for the first time this cycle.",
      sentiment: "positive",
      impact: 1.8,
      created_at: "2026-08-05T00:00:00Z",
    },
    {
      source: "fixture:cpi-print",
      summary: "Core services CPI re-accelerated 0.1pp month-over-month, against expectations.",
      sentiment: "negative",
      impact: 1.2,
      created_at: "2026-08-02T00:00:00Z",
    },
  ],
  forecast: {
    question_id: null,
    market_probability: 0.55,
    vanta_probability: 0.61,
    confidence: 6.5,
    risk_factors: [
      "A single hot CPI print flips the base case",
      "Analog set is small (n=6) — wide confidence interval",
    ],
    edge: 0.06,
  },
};

function StaticChatConsole() {
  return (
    <div>
      <div className="card space-y-5 p-6">
        <div>
          <div className="micro-label">static demo</div>
          <p className="mt-2 text-sm leading-relaxed text-ink-2">
            Static demo — chat needs the live backend. This deployment is a read-only snapshot;
            clone{" "}
            <a
              href="https://github.com/sunkalpchandra/vanta"
              className="text-accent hover:underline"
            >
              sunkalpchandra/vanta
            </a>{" "}
            and run <span className="num">uvicorn app.main:app</span> +{" "}
            <span className="num">npm run dev</span> to stream a real deliberation.
          </p>
        </div>
        <ConsoleFields
          question=""
          category="technology"
          disabled
        />
        <button
          type="button"
          disabled
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white opacity-50"
        >
          Start deliberation
        </button>
      </div>
      <div className="mt-8">
        <div className="micro-label mb-3">example output — not a live run</div>
        <Transcript
          status={EXAMPLE_TRANSCRIPT.status}
          reports={EXAMPLE_TRANSCRIPT.reports}
          evidence={EXAMPLE_TRANSCRIPT.evidence}
          forecast={EXAMPLE_TRANSCRIPT.forecast}
          streaming={false}
        />
      </div>
    </div>
  );
}
