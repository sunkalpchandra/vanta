from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, default=90)
    market_probability: Mapped[float] = mapped_column(Float)
    market_volume_usd: Mapped[float] = mapped_column(Float, default=0.0)
    market_liquidity: Mapped[str] = mapped_column(String(20), default="medium")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    outcome: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 YES, 0 NO
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    agent_reports: Mapped[list["AgentReport"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class Forecast(Base):
    __tablename__ = "forecasts"
    # Every hot read path is "newest forecast for question X" / "newest before
    # T for question X" — the composite index serves both without a scan.
    __table_args__ = (Index("ix_forecasts_question_ts", "question_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)  # 0-10
    reasoning: Mapped[str] = mapped_column(Text)
    risk_factors: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    question: Mapped[Question] = relationship(back_populates="forecasts")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    source: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    sentiment: Mapped[str] = mapped_column(String(20))  # positive | negative | neutral
    impact: Mapped[float] = mapped_column(Float)  # 0-1

    question: Mapped[Question] = relationship(back_populates="evidence")


class AgentReport(Base):
    """One structured report per agent per forecast run — powers Debate Mode."""

    __tablename__ = "agent_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    agent: Mapped[str] = mapped_column(String(40))
    stance: Mapped[str] = mapped_column(String(20))  # bull | bear | neutral
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    argument: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    question: Mapped[Question] = relationship(back_populates="agent_reports")


class WatchlistItem(Base):
    """User-added discovery candidates, merged with the built-in watchlist."""

    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[str] = mapped_column(String(50))
    horizon_days: Mapped[int] = mapped_column(Integer, default=90)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentTrackRecord(Base):
    """Frozen per-agent probability at resolution time — the internal
    forecaster competition. Written by resolve_question from the final
    agent_reports snapshot."""

    __tablename__ = "agent_track_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    agent: Mapped[str] = mapped_column(String(40), index=True)
    probability: Mapped[float] = mapped_column(Float)
    outcome: Mapped[int] = mapped_column(Integer)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Prediction(Base):
    """Resolved historical predictions — powers the accuracy leaderboard."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Null for the seeded reference corpus; set when a live question resolves.
    # Unique: one settled prediction per question, enforced by the database as
    # the backstop against concurrent resolves (NULLs don't collide).
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True, unique=True)
    question_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)
    market_probability: Mapped[float] = mapped_column(Float)
    vanta_probability: Mapped[float] = mapped_column(Float)
    outcome: Mapped[int] = mapped_column(Integer)  # 1 = happened, 0 = didn't
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
