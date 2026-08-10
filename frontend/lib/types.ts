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
