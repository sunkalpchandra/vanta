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
    # Operator credential ("vk_..."), shown once at creation. Gating is off by
    # default (demo); REQUIRE_API_KEY=1 enforces it on mutations.
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Play-money trading balance in vanta credits (ⓥ). Virtual currency only —
    # this is paper trading against real venue prices, never real money.
    balance: Mapped[float] = mapped_column(Float, default=10_000.0)
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


class MarketSnapshot(Base):
    """Point-in-time market price for a question — the market side of the
    market-vs-vanta chart. Question.market_probability mirrors the newest row."""

    __tablename__ = "market_snapshots"
    __table_args__ = (Index("ix_market_snapshots_question_ts", "question_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    probability: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

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


class QuestionNote(Base):
    """Operator annotations on a question — context that isn't evidence
    (resolution criteria clarifications, source caveats, follow-ups)."""

    __tablename__ = "question_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class MarketEvent(Base):
    """A real market ingested from an external venue (Polymarket, Kalshi).
    This is the backtest corpus — deliberately separate from `questions`
    (the curated product surface) so 100k rows can't wreck feed queries or
    the static export. Prices are probabilities of YES in [0,1]."""

    __tablename__ = "market_events"
    __table_args__ = (
        Index("ix_market_events_source_id", "source", "source_id", unique=True),
        Index("ix_market_events_resolved_close", "outcome", "close_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)  # polymarket | kalshi
    source_id: Mapped[str] = mapped_column(String(120))
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)  # normalized, may be "other"
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 YES, 0 NO, NULL unresolved
    volume_usd: Mapped[float] = mapped_column(Float, default=0.0)
    final_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Pre-resolution snapshots — the leakage-free backtest inputs. NULL until
    # the price-history stage fills them (a separate, slower pass).
    price_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Live-trading surface: the sync engine keeps these fresh for active
    # events and flips active off at settlement/delisting.
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    yes_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # current venue YES price
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BacktestPrediction(Base):
    """One leakage-free pipeline run against a resolved MarketEvent: the quant
    pipeline saw ONLY the market price h days before close (plus category
    base rates learned from OTHER events). Scored against the same-time
    market price, so vanta and the market compete on identical information."""

    __tablename__ = "backtest_predictions"
    __table_args__ = (
        Index("ix_backtest_event_horizon", "event_id", "horizon_days", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    horizon_days: Mapped[int] = mapped_column(Integer)  # 7 or 30
    market_probability: Mapped[float] = mapped_column(Float)  # price at T-h
    vanta_probability: Mapped[float] = mapped_column(Float)
    outcome: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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


class Position(Base):
    """A trader's open (or settled) stake in one market event. Play money:
    entry at the synced venue price, settled at the venue outcome."""

    __tablename__ = "positions"
    __table_args__ = (Index("ix_positions_user_event_side", "user_id", "event_id", "side", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    side: Mapped[str] = mapped_column(String(3))  # yes | no
    shares: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)  # per-share cost basis
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    settled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Trade(Base):
    """Append-only execution log — every buy/sell at the then-current price."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    side: Mapped[str] = mapped_column(String(3))  # yes | no
    action: Mapped[str] = mapped_column(String(4))  # buy | sell
    shares: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)  # execution price per share
    cost: Mapped[float] = mapped_column(Float)  # signed balance delta (negative = spent)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PriceTick(Base):
    """A synced venue-price observation for a market event — the series behind
    the market's price chart. Written by the sync engine, one per event per
    sync pass (deduped to at most one per event per hour to bound growth)."""

    __tablename__ = "price_ticks"
    __table_args__ = (Index("ix_price_ticks_event_ts", "event_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    yes_price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AgentTrader(Base):
    """One of vanta's autonomous play-money traders. Each is backed by a bot
    User (user_id) and trades a fixed deterministic strategy over the
    pipeline's forecasts, so it holds Positions and logs Trades through the
    exact same engine as humans — the forecasting edge tested in P&L."""

    __tablename__ = "agent_traders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. "vanta-quant"
    strategy: Mapped[str] = mapped_column(String(40))  # edge | contrarian | confidence
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketWatch(Base):
    """A trader's watch on a market event — powers the per-user watchlist and
    move alerts. Unique per (user, event)."""

    __tablename__ = "market_watches"
    __table_args__ = (Index("ix_market_watches_user_event", "user_id", "event_id", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketComment(Base):
    """A play-money trader's public comment on a market — light social layer.
    Trader handle is the email local-part (never the full email)."""

    __tablename__ = "market_comments"
    __table_args__ = (Index("ix_market_comments_event_ts", "event_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("market_events.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
