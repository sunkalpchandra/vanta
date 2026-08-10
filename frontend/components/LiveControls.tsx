"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";

const SENTIMENTS = ["positive", "negative", "neutral"] as const;

/** Live-backend operator controls: ingest evidence, settle the question.
 * Hidden in the static demo — both actions need the pipeline. */
export function LiveControls({ questionId, resolved }: { questionId: number; resolved: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState("");
  const [summary, setSummary] = useState("");
  const [sentiment, setSentiment] = useState<(typeof SENTIMENTS)[number]>("positive");
  const [impact, setImpact] = useState(0.5);
  const [busy, setBusy] = useState<"evidence" | "resolve" | "market" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [marketPct, setMarketPct] = useState("");

  if (IS_STATIC || resolved) return null;

  async function submitMarket(e: React.FormEvent) {
    e.preventDefault();
    const probability = Number(marketPct) / 100;
    if (!(probability > 0 && probability < 1)) {
      setError("Market price must be between 1 and 99 (%).");
      return;
    }
    setBusy("market");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/market`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ probability }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      // A market move is new information — re-run the pipeline on it.
      await fetch(`${API_URL}/api/questions/${questionId}/refresh`, { method: "POST" });
      setMarketPct("");
      router.refresh();
    } catch {
      setError("Market update failed — is the backend running?");
    } finally {
      setBusy(null);
    }
  }

  async function submitEvidence(e: React.FormEvent) {
    e.preventDefault();
    setBusy("evidence");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/evidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, summary, sentiment, impact }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setOpen(false);
      setSource("");
      setSummary("");
      router.refresh();
    } catch {
      setError("Evidence ingest failed — is the backend running?");
    } finally {
      setBusy(null);
    }
  }

  async function resolve(outcome: boolean) {
    const label = outcome ? "YES" : "NO";
    if (!window.confirm(`Resolve this question ${label}? Forecasting freezes permanently.`)) return;
    setBusy("resolve");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      router.refresh();
    } catch {
      setError("Resolution failed — already resolved?");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card mt-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="micro-label">operator controls</span>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink"
        >
          {open ? "Cancel" : "+ Add evidence"}
        </button>
        <form onSubmit={submitMarket} className="flex items-center gap-1.5">
          <label htmlFor="mkt" className="micro-label">
            market
          </label>
          <input
            id="mkt"
            type="number"
            min={1}
            max={99}
            step={1}
            value={marketPct}
            onChange={(e) => setMarketPct(e.target.value)}
            placeholder="%"
            className="num w-16 rounded-lg border border-line bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy !== null || marketPct === ""}
            className="rounded-lg border border-line px-2.5 py-1.5 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-40"
          >
            {busy === "market" ? "…" : "Set"}
          </button>
        </form>
        <div className="ml-auto flex items-center gap-2">
          <span className="micro-label">settle:</span>
          <button
            onClick={() => resolve(true)}
            disabled={busy !== null}
            className="rounded-lg bg-pos/15 px-3 py-1.5 text-xs font-bold text-pos transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            YES
          </button>
          <button
            onClick={() => resolve(false)}
            disabled={busy !== null}
            className="rounded-lg bg-neg/15 px-3 py-1.5 text-xs font-bold text-neg transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            NO
          </button>
        </div>
      </div>
      {open && (
        <form onSubmit={submitEvidence} className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              required
              minLength={2}
              maxLength={100}
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Source (e.g. FOMC minutes)"
              className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
            />
            <div className="flex items-center gap-3">
              <select
                value={sentiment}
                onChange={(e) => setSentiment(e.target.value as (typeof SENTIMENTS)[number])}
                aria-label="Sentiment"
                className="flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              >
                {SENTIMENTS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <label className="micro-label flex items-center gap-2">
                impact
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={impact}
                  onChange={(e) => setImpact(Number(e.target.value))}
                />
                <span className="num text-ink-2">{impact.toFixed(1)}</span>
              </label>
            </div>
          </div>
          <textarea
            required
            minLength={10}
            maxLength={500}
            rows={2}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="What happened? One or two sentences."
            className="w-full resize-none rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy !== null}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy === "evidence" ? "Re-forecasting…" : "Ingest & re-forecast"}
          </button>
        </form>
      )}
      {error && <p className="mt-3 text-xs text-neg">{error}</p>}
    </div>
  );
}
