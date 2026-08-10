"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";

interface Candidate {
  question: string;
  category: string;
  horizon_days: number;
  rationale: string;
}

/** Autonomous research mode: preview uncovered watchlist signals and mint them. */
export function DiscoveryPanel() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (IS_STATIC) return;
    fetch(`${API_URL}/api/discover/candidates`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, []);

  if (IS_STATIC || candidates === null) return null;
  if (candidates.length === 0) return null;

  async function runDiscovery() {
    setRunning(true);
    setError(false);
    try {
      const res = await fetch(`${API_URL}/api/discover?count=3`, { method: "POST" });
      if (!res.ok) throw new Error();
      router.push("/");
      router.refresh();
    } catch {
      setError(true);
      setRunning(false);
    }
  }

  return (
    <div className="card mt-8 p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="micro-label">autonomous research mode</div>
          <p className="mt-1 text-sm text-ink-2">
            {candidates.length} watchlist signal{candidates.length === 1 ? "" : "s"} not yet covered
            by the question base.
          </p>
        </div>
        <button
          onClick={runDiscovery}
          disabled={running}
          className="shrink-0 rounded-lg border border-accent px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent hover:text-white disabled:opacity-50"
        >
          {running ? "Minting…" : "Run discovery"}
        </button>
      </div>
      <ul className="mt-4 space-y-2">
        {candidates.slice(0, 3).map((c) => (
          <li key={c.question} className="text-sm">
            <span className="text-ink">{c.question}</span>
            <p className="mt-0.5 text-xs text-muted">{c.rationale}</p>
          </li>
        ))}
      </ul>
      <WatchlistForm onAdded={() => refreshCandidates()} />
      {error && <p className="mt-3 text-xs text-neg">Discovery failed — is the backend running?</p>}
    </div>
  );

  function refreshCandidates() {
    fetch(`${API_URL}/api/discover/candidates`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setCandidates)
      .catch(() => undefined);
  }
}

function WatchlistForm({ onAdded }: { onAdded: () => void }) {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<"idle" | "busy" | "dup" | "err">("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("busy");
    try {
      const res = await fetch(`${API_URL}/api/discover/watchlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (res.status === 409) {
        setStatus("dup");
        return;
      }
      if (!res.ok) throw new Error();
      setQuestion("");
      setStatus("idle");
      onAdded();
    } catch {
      setStatus("err");
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
      <input
        required
        minLength={10}
        maxLength={500}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Point the agents at a signal — phrase it as a yes/no question"
        aria-label="Add to watchlist"
        className="min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
      />
      <button
        type="submit"
        disabled={status === "busy"}
        className="rounded-lg border border-line px-3 py-2 text-xs font-semibold text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
      >
        {status === "busy" ? "Adding…" : "+ Watch"}
      </button>
      {status === "dup" && <span className="w-full text-xs text-muted">Already on the watchlist.</span>}
      {status === "err" && <span className="w-full text-xs text-neg">Couldn&apos;t add — backend running?</span>}
    </form>
  );
}
