// Server-side data access. Two modes:
//  - live:   fetch from the FastAPI backend (SSR uses API_URL_INTERNAL when
//            the server reaches the API by a different route than the browser,
//            e.g. http://api:8000 inside docker compose)
//  - static: read the baked snapshot from public/data (GitHub Pages demo)
// Only server components may import this module.

import { API_URL } from "./api";
import { IS_STATIC } from "./config";
import type {
  RealBacktestOut,
  AgentCalibrationBin,
  AgentLeaderboardRow,
  AgentRecord,
  AlertItem,
  BacktestOut,
  BriefItem,
  CalibrationBin,
  CategoryOut,
  ChangesOut,
  FeedCard,
  HistoryPoint,
  LeaderboardRow,
  MarketPoint,
  MoverCard,
  PredictionOut,
  QuestionDetail,
  QuestionOut,
  RelatedQuestion,
  SensitivityItem,
  StatsOut,
} from "./types";

const SSR_API_URL = process.env.API_URL_INTERNAL ?? API_URL;

async function readSnapshot<T>(name: string, fallback: T): Promise<T> {
  try {
    const { promises: fs } = await import("fs");
    const { join } = await import("path");
    const file = join(process.cwd(), "public", "data", name);
    return JSON.parse(await fs.readFile(file, "utf8")) as T;
  } catch {
    return fallback;
  }
}

async function get<T>(path: string, snapshotName: string, fallback: T): Promise<T> {
  if (IS_STATIC) return readSnapshot(snapshotName, fallback);
  try {
    const res = await fetch(`${SSR_API_URL}${path}`, { cache: "no-store" });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback; // backend offline — pages render their empty states
  }
}

export const getFeed = () => get<FeedCard[]>("/api/feed", "feed.json", []);
export const getQuestions = () => get<QuestionOut[]>("/api/questions", "questions.json", []);
export const getQuestion = (id: string) =>
  get<QuestionDetail | null>(`/api/questions/${id}`, `questions/${id}.json`, null);
export const getHistory = (id: string) =>
  get<HistoryPoint[]>(`/api/questions/${id}/history`, `history/${id}.json`, []);
export const getMarketHistory = (id: string) =>
  get<MarketPoint[]>(`/api/questions/${id}/market-history`, `market-history/${id}.json`, []);
export const getLeaderboard = () => get<LeaderboardRow[]>("/api/leaderboard", "leaderboard.json", []);
export const getBrief = () => get<BriefItem[]>("/api/brief", "brief.json", []);
export const getStats = () => get<StatsOut | null>("/api/stats", "stats.json", null);
export const getRealBacktest = (horizon: 7 | 30) =>
  get<RealBacktestOut | null>(
    `/api/backtest/real?horizon=${horizon}`,
    `backtest-real-${horizon}.json`,
    null,
  );
export const getCalibration = () =>
  get<CalibrationBin[]>("/api/leaderboard/calibration", "calibration.json", []);
export const getCategories = () => get<CategoryOut[]>("/api/categories", "categories.json", []);
export const getPredictions = () =>
  get<PredictionOut[]>("/api/leaderboard/predictions", "predictions.json", []);
export const getMovers = () => get<MoverCard[]>("/api/feed/movers", "movers.json", []);
export const getAgentLeaderboard = () =>
  get<AgentLeaderboardRow[]>("/api/agents/leaderboard", "agents.json", []);
export const getBacktest = () => get<BacktestOut | null>("/api/quant/backtest", "backtest.json", null);
export const getSparklines = () =>
  get<Record<string, number[]>>("/api/feed/sparklines", "sparklines.json", {});
export const getRelated = (id: string) =>
  get<RelatedQuestion[]>(`/api/questions/${id}/related`, `related/${id}.json`, []);
export const getAlerts = () => get<AlertItem[]>("/api/alerts", "alerts.json", []);
export const getAgentRecords = (name: string) =>
  get<AgentRecord[]>(`/api/agents/${name}/records`, `agent-records/${name}.json`, []);
export const getAgentCalibration = (name: string) =>
  get<AgentCalibrationBin[]>(`/api/agents/${name}/calibration`, `agent-calibration/${name}.json`, []);
export const getChanges = (id: string) =>
  get<ChangesOut | null>(`/api/questions/${id}/changes`, `changes/${id}.json`, null);
export const getSensitivity = (id: string) =>
  get<{ items: SensitivityItem[] }>(
    `/api/questions/${id}/sensitivity`,
    `sensitivity/${id}.json`,
    { items: [] },
  );
