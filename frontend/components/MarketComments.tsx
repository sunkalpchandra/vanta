"use client";

import { useEffect, useState } from "react";
import { IS_STATIC } from "@/lib/config";
import {
  type Comment,
  deleteComment,
  getComments,
  MAX_BODY,
  postComment,
  validateBody,
} from "@/lib/comments";
import { shortDate } from "@/lib/format";
import { ensureTrader, getTraderKey } from "@/lib/trader";

const DISCLAIMER = "play money · paper trading · real market prices";

type ViewState = "loading" | "error" | "ready";

/**
 * A per-market discussion thread. Reads are public (GET /api/markets/{id}/
 * comments); posting and deleting need the trader identity held in this browser
 * (the X-API-Key from POST /api/users). Newest-first, with a post box that
 * onboards a play-money account inline via ensureTrader when there's no key yet,
 * and a delete affordance on the caller's own comments.
 *
 * Static demo (IS_STATIC) has no trading backend, so the thread renders an
 * honest read-only note instead of trying to fetch. Loading/empty/error are all
 * handled explicitly.
 *
 * Play money only — virtual ⓥ credits, real venue prices, never real money.
 */
export function MarketComments({ eventId }: { eventId: number }) {
  const [state, setState] = useState<ViewState>("loading");
  const [comments, setComments] = useState<Comment[]>([]);
  // Hydration-safe: read localStorage only after mount.
  const [hasKey, setHasKey] = useState(false);
  const [email, setEmail] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Comments this session authored (precise delete affordance) plus the handle
  // learned from a post — lets us also offer delete on the caller's earlier
  // comments in this thread. The backend is the real guard (403 otherwise).
  const [mine, setMine] = useState<Set<number>>(new Set());
  const [myHandle, setMyHandle] = useState<string | null>(null);

  useEffect(() => {
    if (IS_STATIC) return;
    setHasKey(getTraderKey() !== null);
    let cancelled = false;
    getComments(eventId)
      .then((rows) => {
        if (cancelled) return;
        setComments(rows);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  if (IS_STATIC) {
    return (
      <section aria-label="Discussion" className="card p-6 text-center text-sm text-muted">
        The static demo has no trading backend, so the discussion is read-only here. Run the backend
        locally to post and delete comments.
        <div className="micro-label mt-3">{DISCLAIMER}</div>
      </section>
    );
  }

  const canDelete = (c: Comment) => mine.has(c.id) || (myHandle !== null && c.handle === myHandle);
  const cleaned = validateBody(draft);
  const draftValid = cleaned !== null;

  async function register(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await ensureTrader(email);
      setHasKey(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed — is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draftValid) return;
    setBusy(true);
    setError(null);
    try {
      const created = await postComment(eventId, draft);
      setComments((cur) => [created, ...cur]);
      setMine((cur) => new Set(cur).add(created.id));
      setMyHandle(created.handle);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't post — is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    // Optimistic removal; restore on failure so a 403/network error is honest.
    const prev = comments;
    setComments((cur) => cur.filter((c) => c.id !== id));
    try {
      await deleteComment(eventId, id);
    } catch (err) {
      setComments(prev);
      setError(err instanceof Error ? err.message : "Couldn't delete that comment.");
    }
  }

  return (
    <section aria-label="Discussion">
      <div className="micro-label mb-3">
        discussion · {comments.length} {comments.length === 1 ? "comment" : "comments"}
      </div>

      {hasKey ? (
        <form onSubmit={submit} className="mb-4">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={MAX_BODY}
            rows={3}
            placeholder="Share your read on this market…"
            aria-label="Write a comment"
            className="w-full resize-y rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <div className="mt-2 flex items-center justify-between gap-3">
            <span className="micro-label">
              {draft.trim().length}/{MAX_BODY}
            </span>
            <button
              type="submit"
              disabled={busy || !draftValid}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy ? "Posting…" : "Post comment"}
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={register} className="mb-4 flex flex-wrap items-center gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-label="Email for your play-money account"
            className="w-56 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Join the discussion"}
          </button>
          <p className="w-full text-xs text-muted">
            Free play-money account — your trading key is stored in this browser only.
          </p>
        </form>
      )}

      {error && (
        <p role="alert" className="mb-3 text-xs text-neg">
          {error}
        </p>
      )}

      {state === "loading" ? (
        <div className="card p-6 text-center text-sm text-muted">Loading the discussion…</div>
      ) : state === "error" ? (
        <div className="card p-6 text-center text-sm text-muted">
          Couldn&apos;t load the discussion — is the backend running?
        </div>
      ) : comments.length === 0 ? (
        <div className="card p-6 text-center text-sm text-muted">
          No comments yet. {hasKey ? "Be the first to weigh in." : "Join the discussion to weigh in."}
        </div>
      ) : (
        <ul className="card divide-y divide-line/60">
          {comments.map((c) => (
            <li key={c.id} className="px-5 py-3">
              <div className="mb-1 flex items-center gap-2">
                <span className="text-sm font-semibold text-ink">{c.handle}</span>
                <span className="num text-xs text-muted">{shortDate(c.created_at)}</span>
                {canDelete(c) && (
                  <button
                    type="button"
                    onClick={() => remove(c.id)}
                    aria-label="Delete your comment"
                    className="ml-auto text-xs text-muted transition-colors hover:text-neg"
                  >
                    Delete
                  </button>
                )}
              </div>
              <p className="whitespace-pre-wrap break-words text-sm text-ink-2">{c.body}</p>
            </li>
          ))}
        </ul>
      )}

      <p className="micro-label mt-4">{DISCLAIMER}</p>
    </section>
  );
}
