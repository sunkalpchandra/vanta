"use client";

import { useCallback, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";

type Note = { id: number; body: string; created_at: string };

/** Operator annotations on a question — resolution-criteria clarifications,
 * source caveats, follow-ups. Live backend only: the static demo has no
 * operator, so the panel hides itself there. */
export function NotesPanel({ questionId }: { questionId: number }) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/notes`);
      if (res.ok) setNotes(await res.json());
    } catch {
      // backend unreachable — leave the panel in its empty state
    }
  }, [questionId]);

  useEffect(() => {
    if (!IS_STATIC) load();
  }, [load]);

  if (IS_STATIC || notes === null) return null;

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (draft.trim().length < 3) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: draft.trim() }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setDraft("");
      await load();
    } catch (err) {
      setError(`Could not save note (${err instanceof Error ? err.message : "error"}).`);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/questions/${questionId}/notes/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      await load();
    } catch (err) {
      setError(`Could not delete note (${err instanceof Error ? err.message : "error"}).`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-5" aria-label="Operator notes">
      <h2 className="micro-label">Operator notes</h2>
      {notes.length === 0 ? (
        <p className="mt-3 text-sm text-muted">No notes yet.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-2 text-sm text-ink-2">
              <span className="flex-1 leading-snug">{n.body}</span>
              <button
                onClick={() => remove(n.id)}
                disabled={busy}
                aria-label="Delete note"
                className="micro-label !text-muted hover:!text-ink"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="mt-3 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a note (e.g. resolution caveat)…"
          aria-label="New note"
          maxLength={1000}
          className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
        />
        <button
          type="submit"
          disabled={busy || draft.trim().length < 3}
          className="micro-label rounded-lg border border-line px-3 py-1.5 !text-ink-2 hover:border-accent/50 disabled:opacity-40"
        >
          Save
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </section>
  );
}
