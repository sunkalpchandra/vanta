from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    summary: str
    sentiment: str
    impact: float


class AgentReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent: str
    stance: str
    probability: float | None
    argument: str
    details: dict


class ForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    probability: float
    confidence: float
    reasoning: str
    risk_factors: list
    timestamp: datetime


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    category: str
    horizon_days: int
    market_probability: float
    market_volume_usd: float
    market_liquidity: str
    created_at: datetime


class QuestionDetail(QuestionOut):
    latest_forecast: ForecastOut | None = None
    evidence: list[EvidenceOut] = []
    agent_reports: list[AgentReportOut] = []


class FeedCard(BaseModel):
    question_id: int
    question: str
    category: str
    market_probability: float
    vanta_probability: float
    confidence: float
    edge: float
    horizon_days: int
    headline: str


class HistoryPoint(BaseModel):
    timestamp: datetime
    probability: float


class LeaderboardRow(BaseModel):
    category: str
    n_resolved: int
    vanta_accuracy: float
    market_accuracy: float
    vanta_brier: float
    market_brier: float


class BriefItem(BaseModel):
    rank: int
    question_id: int
    question: str
    category: str
    market_probability: float
    vanta_probability: float
    edge: float
    one_liner: str


class AskRequest(BaseModel):
    question: str = Field(min_length=10, max_length=500)
    category: str = "technology"
    horizon_days: int = Field(default=90, ge=1, le=1000)
    market_probability: float | None = Field(default=None, gt=0, lt=1)
