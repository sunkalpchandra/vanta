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
  avg_abs_edge: number | null;
  llm_narratives: boolean;
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
  edge: number;
  one_liner: string;
}
