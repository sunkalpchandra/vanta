"""Forecasting service: binds the agent pipeline to persistence."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .agents.base import QuestionContext
from .agents.historian import base_rate_for
from .agents.orchestrator import PipelineResult, run_pipeline
from .models import (
    AgentReport,
    AgentTrackRecord,
    Evidence,
    Forecast,
    MarketSnapshot,
    Prediction,
    Question,
    utcnow,
)


def learned_base_rate(db: Session, category: str, pseudo_count: float = 20.0) -> float:
    """Static category prior blended with the observed resolved record.

    The static prior acts as `pseudo_count` phantom resolutions, so the
    observed rate takes over gradually as real resolutions accumulate:
    (static * k + observed_yes) / (k + n).
    """
    static = base_rate_for(category)
    rows = db.execute(
        select(Prediction.outcome).where(Prediction.category == category)
    ).all()
    n = len(rows)
    if n == 0:
        return static
    observed_yes = sum(outcome for (outcome,) in rows)
    return (static * pseudo_count + observed_yes) / (pseudo_count + n)


def build_context(db: Session, question: Question, evidence: list[Evidence]) -> QuestionContext:
    return QuestionContext(
        question=question.question,
        category=question.category,
        horizon_days=question.horizon_days,
        market_probability=question.market_probability,
        market_volume_usd=question.market_volume_usd,
        market_liquidity=question.market_liquidity,
        evidence=[
            {"source": e.source, "summary": e.summary, "sentiment": e.sentiment, "impact": e.impact}
            for e in evidence
        ],
        base_rate=round(learned_base_rate(db, question.category), 4),
    )


def run_and_store_forecast(db: Session, question: Question) -> tuple[Forecast, PipelineResult]:
    """Run the full agent pipeline for a question and persist the results."""
    result = run_pipeline(build_context(db, question, question.evidence))

    # The pipeline can take a while (LLM narratives): a resolve may have landed
    # since the caller's guard. Re-check before touching the frozen record.
    resolved_now = db.scalar(select(Question.resolved).where(Question.id == question.id))
    if resolved_now:
        raise ResolutionError("question was resolved while the pipeline ran; forecast discarded")

    # Replace prior agent reports; keep forecast history append-only.
    db.query(AgentReport).filter(AgentReport.question_id == question.id).delete()
    for output in result.outputs:
        db.add(
            AgentReport(
                question_id=question.id,
                agent=output.agent,
                stance=output.stance,
                probability=output.probability,
                argument=output.argument,
                details=output.details,
            )
        )
    forecast = Forecast(
        question_id=question.id,
        probability=result.probability,
        confidence=result.confidence,
        reasoning=result.reasoning,
        risk_factors=result.risk_factors,
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast, result


def create_question(
    db: Session,
    text: str,
    category: str,
    horizon_days: int,
    market_probability: float | None = None,
    market_volume_usd: float = 0.0,
    market_liquidity: str = "low",
    evidence: list[tuple[str, str, str, float]] | None = None,
) -> Question:
    """Create a question. Without a quoted market, the category base rate
    stands in as the market prior (flagged by zero volume / low liquidity)."""
    question = Question(
        question=text,
        category=category,
        horizon_days=horizon_days,
        market_probability=market_probability if market_probability is not None else base_rate_for(category),
        market_volume_usd=market_volume_usd,
        market_liquidity=market_liquidity,
    )
    db.add(question)
    db.flush()
    for source, summary, sentiment, impact in evidence or []:
        db.add(
            Evidence(
                question_id=question.id,
                source=source,
                summary=summary,
                sentiment=sentiment,
                impact=impact,
            )
        )
    db.commit()
    db.refresh(question)
    return question


def evidence_sensitivity(db: Session, question: Question) -> list[dict]:
    """Leave-one-out evidence importance: re-run the pipeline without each
    evidence item and report how much the final probability moves. Narratives
    are suppressed — these counterfactual runs only need the numbers."""
    evidence = list(question.evidence)
    if not evidence:
        return []
    base_ctx = build_context(db, question, evidence)
    base_ctx.narratives = False
    full_probability = run_pipeline(base_ctx).probability

    items: list[dict] = []
    for leave_out in evidence:
        remaining = [e for e in evidence if e.id != leave_out.id]
        ctx = build_context(db, question, remaining)
        ctx.narratives = False
        without = run_pipeline(ctx).probability
        items.append(
            {
                "source": leave_out.source,
                "summary": leave_out.summary,
                "sentiment": leave_out.sentiment,
                "impact": leave_out.impact,
                # Positive delta: this item pushes the forecast UP by this much.
                "delta": round(full_probability - without, 4),
            }
        )
    items.sort(key=lambda item: abs(item["delta"]), reverse=True)
    return items


class ResolutionError(ValueError):
    """Raised when a question cannot be resolved (already resolved / no forecast)."""


def record_market_price(db: Session, question: Question, probability: float) -> MarketSnapshot:
    """Ingest a new market price: append a snapshot and mirror it onto the
    question. The pipeline is NOT re-run here — callers decide whether the
    move warrants a re-forecast (the operator UI does both)."""
    if question.resolved:
        raise ResolutionError("question is resolved; the market is settled")
    snapshot = MarketSnapshot(question_id=question.id, probability=probability)
    question.market_probability = probability
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    db.refresh(question)
    return snapshot


def resolve_question(db: Session, question: Question, outcome: bool) -> Prediction:
    """Settle a question: freeze vanta's final call against the actual outcome
    and write the resolved Prediction row that feeds the accuracy leaderboard.

    Concurrency-safe: the freeze is a guarded UPDATE (only one caller can flip
    resolved 0->1), and the unique index on predictions.question_id backstops
    the insert at the database level."""
    latest = db.scalar(
        select(Forecast)
        .where(Forecast.question_id == question.id)
        .order_by(Forecast.timestamp.desc())
        .limit(1)
    )
    if latest is None:
        raise ResolutionError("question has no forecast to score")

    resolved_at = utcnow()
    claimed = db.execute(
        update(Question)
        .where(Question.id == question.id, Question.resolved.is_(False))
        .values(resolved=True, outcome=int(outcome), resolved_at=resolved_at)
    ).rowcount
    if claimed == 0:
        db.rollback()
        raise ResolutionError("question is already resolved")

    prediction = Prediction(
        question_id=question.id,
        question_text=question.question,
        category=question.category,
        market_probability=question.market_probability,
        vanta_probability=latest.probability,
        outcome=int(outcome),
        resolved_at=resolved_at,
    )
    db.add(prediction)
    # Freeze each agent's final call — the internal forecaster competition.
    reports = db.scalars(select(AgentReport).where(AgentReport.question_id == question.id)).all()
    for report in reports:
        if report.probability is None:
            continue  # skeptic (and abstaining agents) never estimate
        db.add(
            AgentTrackRecord(
                question_id=question.id,
                agent=report.agent,
                probability=report.probability,
                outcome=int(outcome),
                resolved_at=resolved_at,
            )
        )
    try:
        db.commit()
    except IntegrityError as exc:  # unique(question_id) — a concurrent resolve won
        db.rollback()
        raise ResolutionError("question is already resolved") from exc
    db.refresh(prediction)
    db.refresh(question)
    return prediction
