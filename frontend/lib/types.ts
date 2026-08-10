export interface ForecastOut {
  probability: number;
  confidence: number;
  reasoning: string;
  risk_factors: string[];
  timestamp: string;
}

export interface EvidenceOut {
  source: string;
  summary: string;
  sentiment: "positive" | "negative" | "neutral";
  impact: number;
  created_at: string;
}

export interface AgentReportOut {
  agent: string;
  stance: "bull" | "bear" | "neutral";
  probability: number | null;
  argument: string;
  details: Record<string, unknown>;
}

export interface QuestionOut {
  id: number;
  question: string;
  category: string;
  horizon_days: number;
  market_probability: number;
  market_volume_usd: number;
  market_liquidity: string;
  resolved: boolean;
  outcome: number | null;
  created_at: string;
}

export interface QuestionDetail extends QuestionOut {
  latest_forecast: ForecastOut | null;
  evidence: EvidenceOut[];
  agent_reports: AgentReportOut[];
  difficulty: number | null;
}

export interface FeedCard {
  question_id: number;
  question: string;
  category: string;
  market_probability: number;
  vanta_probability: number;
  confidence: number;
  edge: number;
  horizon_days: number;
  headline: string;
}

export interface HistoryPoint {
  timestamp: string;
  probability: number;
}

export interface MarketPoint {
  timestamp: string;
  probability: number;
}

export interface LeaderboardRow {
  category: string;
  n_resolved: number;
  vanta_accuracy: number;
  market_accuracy: number;
  vanta_brier: number;
  market_brier: number;
}

export interface StatsOut {
  n_live_questions: number;
  n_resolved: number;
  vanta_accuracy: number | null;
  market_accuracy: number | null;
  vanta_brier: number | null;
  market_brier: number | null;
  vanta_log_score: number | null;
  market_log_score: number | null;
  vanta_reliability: number | null;
  vanta_resolution: number | null;
  outcome_uncertainty: number | null;
  avg_abs_edge: number | null;
  llm_narratives: boolean;
}

export interface MoverCard {
  question_id: number;
  question: string;
  category: string;
  current: number;
  previous: number;
  delta: number;
  window_days: number;
}

export interface RelatedQuestion {
  id: number;
  question: string;
  category: string;
  similarity: number;
  resolved: boolean;
}

export interface AlertItem {
  kind: "edge" | "move";
  question_id: number;
  question: string;
  category: string;
  value: number;
  detail: string;
}

export interface AgentRecord {
  question_id: number;
  question: string;
  probability: number;
  outcome: number;
  abs_error: number;
}

export interface SensitivityItem {
  source: string;
  summary: string;
  sentiment: string;
  impact: number;
  delta: number;
}

export interface BacktestOut {
  n_events: number;
  n_covered: number;
  coverage: number;
  accuracy: number | null;
  brier: number | null;
  log_score: number | null;
  baseline_brier: number;
}

export interface AgentLeaderboardRow {
  agent: string;
  n_resolved: number;
  accuracy: number;
  brier: number;
  log_score: number;
}

export interface CategoryOut {
  category: string;
  base_rate: number;
  n_live_questions: number;
  n_resolved: number;
}

export interface CalibrationBin {
  mid: number;
  vanta_mean_predicted: number | null;
  vanta_observed_rate: number | null;
  vanta_count: number;
  market_mean_predicted: number | null;
  market_observed_rate: number | null;
  market_count: number;
}

export interface BriefItem {
  rank: number;
  question_id: number;
  question: string;
  category: string;
  market_probability: number;
  vanta_probability: number;
  confidence: number;
  edge: number;
  one_liner: string;
}

export interface PredictionOut {
  question_id: number | null;
  question_text: string;
  category: string;
  market_probability: number;
  vanta_probability: number;
  outcome: number;
  resolved_at: string;
}
