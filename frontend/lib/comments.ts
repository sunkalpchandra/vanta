// Per-market discussion thread for the play-money prediction market. Public
// read (GET /api/markets/{id}/comments); authenticated write/delete via the
// trader's X-API-Key (the identity held in this browser by lib/trader). A
// comment is addressed by the author's handle — the email local-part — never a
// full email. Play money only: virtual ⓥ credits, paper trading at real venue
// prices, never real money.

import { API_URL } from "./api";
import { authHeaders, readableError, type TraderStorage } from "./trader";

export interface Comment {
  id: number;
  handle: string; // email local-part — never a full email
  body: string;
  created_at: string;
}

/** Longest comment the backend accepts (Field max_length=1000). */
export const MAX_BODY = 1000;

/**
 * Validate/normalize a comment body exactly the way the backend does: trim,
 * then require 1..MAX_BODY characters. Returns the cleaned string, or null when
 * it is empty (after trimming) or too long. Pure and total — the post box's
 * gate, kept in lockstep with the CommentIn validator on the server.
 */
export function validateBody(s: string): string | null {
  const trimmed = s.trim();
  if (trimmed.length < 1 || trimmed.length > MAX_BODY) return null;
  return trimmed;
}

interface CommentsDeps {
  fetchImpl?: typeof fetch;
  storage?: TraderStorage;
}

/**
 * Newest-first comments on a market. Public — no identity needed. Throws a
 * readable Error on a non-ok response so the thread can surface it.
 */
export async function getComments(
  eventId: number,
  limit = 50,
  deps: CommentsDeps = {},
): Promise<Comment[]> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/markets/${eventId}/comments?limit=${limit}`);
  if (!res.ok) throw new Error(await readableError(res, `couldn't load comments (${res.status})`));
  return (await res.json()) as Comment[];
}

/**
 * Post a comment. Requires a trader identity (throws before any network call
 * when there is none). Validates/normalizes the body locally the same way the
 * backend does, then POSTs it with the trader key. Returns the created comment.
 */
export async function postComment(
  eventId: number,
  body: string,
  deps: CommentsDeps = {},
): Promise<Comment> {
  const headers = authHeaders(deps.storage);
  if (!("X-API-Key" in headers)) throw new Error("start trading to join the discussion");
  const clean = validateBody(body);
  if (clean === null) throw new Error(`comment must be 1–${MAX_BODY} characters`);
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/markets/${eventId}/comments`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ body: clean }),
  });
  if (!res.ok) throw new Error(await readableError(res, `couldn't post comment (${res.status})`));
  return (await res.json()) as Comment;
}

/**
 * Delete a comment. Requires a trader identity; the backend enforces that only
 * the author may delete (403 otherwise). Resolves true on a 204, and treats a
 * 404 as already-gone. Throws on any other failure (including the 403).
 */
export async function deleteComment(
  eventId: number,
  commentId: number,
  deps: CommentsDeps = {},
): Promise<boolean> {
  const headers = authHeaders(deps.storage);
  if (!("X-API-Key" in headers)) throw new Error("start trading to manage your comments");
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch(`${API_URL}/api/markets/${eventId}/comments/${commentId}`, {
    method: "DELETE",
    headers,
  });
  if (res.ok || res.status === 404) return true;
  throw new Error(await readableError(res, `couldn't delete comment (${res.status})`));
}
