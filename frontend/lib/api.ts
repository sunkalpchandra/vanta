import type {
  BriefItem,
  FeedCard,
  HistoryPoint,
  LeaderboardRow,
  QuestionDetail,
  QuestionOut,
} from "./types";

// Browser-facing base URL: client-side fetches (AskForm) and links the browser
// follows (share cards).
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Server-side rendering may need a different route to the API than the browser
// does — inside docker compose, "localhost:8000" points at the web container
// itself, so SSR uses API_URL_INTERNAL (http://api:8000) when set. In the
// browser bundle this env var is undefined and we fall back to the public URL.
const SSR_API_URL = process.env.API_URL_INTERNAL ?? API_URL;

async function get<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${SSR_API_URL}${path}`, { cache: "no-store" });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback; // backend offline — pages render their empty states
  }
}

export const getFeed = () => get<FeedCard[]>("/api/feed", []);
export const getQuestions = () => get<QuestionOut[]>("/api/questions", []);
export const getQuestion = (id: string) => get<QuestionDetail | null>(`/api/questions/${id}`, null);
export const getHistory = (id: string) => get<HistoryPoint[]>(`/api/questions/${id}/history`, []);
export const getLeaderboard = () => get<LeaderboardRow[]>("/api/leaderboard", []);
export const getBrief = () => get<BriefItem[]>("/api/brief", []);
