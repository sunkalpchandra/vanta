from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


def _to_utc_iso(value: datetime) -> str:
    """Serialize as zone-qualified UTC. SQLite returns naive datetimes even for
    DateTime(timezone=True) columns; without an explicit offset, JS Date()
    parses them as local time and shifts every chart date by the viewer's UTC
    offset."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UTCDateTime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=str)]

Category = Literal["technology", "finance", "politics", "science", "sports", "crypto"]


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
    timestamp: UTCDateTime


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    category: str
    horizon_days: int
    market_probability: float
    market_volume_usd: float
    market_liquidity: str
    resolved: bool = False
    outcome: int | None = None
    created_at: UTCDateTime


class QuestionDetail(QuestionOut):
    latest_forecast: ForecastOut | None = None
    evidence: list[EvidenceOut] = []
    agent_reports: list[AgentReportOut] = []


class MoverCard(BaseModel):
    question_id: int
    question: str
    category: str
    current: float
    previous: float
    delta: float
    window_days: int


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
    timestamp: UTCDateTime
    probability: float


class LeaderboardRow(BaseModel):
    category: str
    n_resolved: int
    vanta_accuracy: float
    market_accuracy: float
    vanta_brier: float
    market_brier: float


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int | None
    question_text: str
    category: str
    market_probability: float
    vanta_probability: float
    outcome: int
    resolved_at: UTCDateTime


class StatsOut(BaseModel):
    n_live_questions: int
    n_resolved: int
    vanta_accuracy: float | None
    market_accuracy: float | None
    vanta_brier: float | None
    market_brier: float | None
    vanta_log_score: float | None
    market_log_score: float | None
    vanta_reliability: float | None
    vanta_resolution: float | None
    outcome_uncertainty: float | None
    avg_abs_edge: float | None
    llm_narratives: bool


class BacktestOut(BaseModel):
    n_events: int
    n_covered: int
    coverage: float
    accuracy: float | None
    brier: float | None
    log_score: float | None
    baseline_brier: float


class AgentLeaderboardRow(BaseModel):
    agent: str
    n_resolved: int
    accuracy: float
    brier: float
    log_score: float


class CategoryOut(BaseModel):
    category: str
    base_rate: float
    n_live_questions: int
    n_resolved: int


class CalibrationBinOut(BaseModel):
    mid: float
    vanta_mean_predicted: float | None
    vanta_observed_rate: float | None
    vanta_count: int
    market_mean_predicted: float | None
    market_observed_rate: float | None
    market_count: int


class BriefItem(BaseModel):
    rank: int
    question_id: int
    question: str
    category: str
    market_probability: float
    vanta_probability: float
    confidence: float
    edge: float
    one_liner: str


class ResolveRequest(BaseModel):
    outcome: bool


class EvidenceIn(BaseModel):
    source: str = Field(min_length=2, max_length=100)
    summary: str = Field(min_length=10, max_length=500)
    sentiment: Literal["positive", "negative", "neutral"]
    impact: float = Field(ge=0.0, le=1.0)


class DiscoveredQuestion(BaseModel):
    question: QuestionOut
    rationale: str


class WatchlistIn(BaseModel):
    question: str = Field(min_length=10, max_length=500)
    category: Category = "technology"
    horizon_days: int = Field(default=90, ge=1, le=1000)
    rationale: str = Field(default="", max_length=500)


class AskRequest(BaseModel):
    question: str = Field(min_length=10, max_length=500)
    category: Category = "technology"
    horizon_days: int = Field(default=90, ge=1, le=1000)
    market_probability: float | None = Field(default=None, gt=0, lt=1)
