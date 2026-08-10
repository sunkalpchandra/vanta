"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import type { QuestionDetail } from "@/lib/types";

const CATEGORIES = ["technology", "finance", "politics", "science", "sports", "crypto"];

export function AskForm() {
  if (IS_STATIC) {
    return (
      <div className="card p-6">
        <div className="micro-label">static demo</div>
        <p className="mt-2 text-sm leading-relaxed text-ink-2">
          This deployment is a read-only snapshot — asking a new question runs the seven-agent
          pipeline, which needs the live backend. Clone{" "}
          <a
            href="https://github.com/sunkalpchandra/vanta"
            className="text-accent hover:underline"
          >
            sunkalpchandra/vanta
          </a>{" "}
          and run <span className="num">uvicorn app.main:app</span> +{" "}
          <span className="num">npm run dev</span> to forecast your own questions.
        </p>
      </div>
    );
  }
  return <LiveAskForm />;
}

function LiveAskForm() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState("technology");
  const [horizon, setHorizon] = useState(90);
  const [status, setStatus] = useState<"idle" | "running" | "error">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("running");
    try {
      const res = await fetch(`${API_URL}/api/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, category, horizon_days: horizon }),
      });
      if (!res.ok) throw new Error(await res.text());
      const created = (await res.json()) as QuestionDetail;
      router.push(`/questions/${created.id}`);
    } catch {
      setStatus("error");
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-5 p-6">
      <div>
        <label htmlFor="q" className="micro-label">
          Question
        </label>
        <textarea
          id="q"
          required
          minLength={10}
          maxLength={500}
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder='e.g. "Will Apple stock rise after its next earnings report?"'
          className="mt-2 w-full resize-none rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
        />
        <p className="mt-1.5 text-xs text-muted">
          Phrase it as a yes/no event with a clear resolution — the agent pipeline forecasts the
          probability of YES.
        </p>
      </div>
      <div className="flex flex-wrap gap-5">
        <div>
          <label htmlFor="cat" className="micro-label">
            Category
          </label>
          <select
            id="cat"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-2 block rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="hz" className="micro-label">
            Horizon (days)
          </label>
          <input
            id="hz"
            type="number"
            min={1}
            max={1000}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="num mt-2 block w-28 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={status === "running"}
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {status === "running" ? "Agents deliberating…" : "Generate forecast"}
        </button>
        {status === "running" && (
          <span className="text-xs text-muted">
            research → quant → market → sentiment → historian → skeptic → synthesis
          </span>
        )}
        {status === "error" && (
          <span className="text-xs text-neg">Forecast failed — is the backend running?</span>
        )}
      </div>
    </form>
  );
}
