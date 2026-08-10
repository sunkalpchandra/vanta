"""Forecasting service: binds the agent pipeline to persistence."""

from sqlalchemy.orm import Session

from .agents.base import QuestionContext
from .agents.historian import base_rate_for
from .agents.orchestrator import PipelineResult, run_pipeline
from .models import AgentReport, Evidence, Forecast, Question


def build_context(question: Question, evidence: list[Evidence]) -> QuestionContext:
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
    )


def run_and_store_forecast(db: Session, question: Question) -> tuple[Forecast, PipelineResult]:
    """Run the full agent pipeline for a question and persist the results."""
    result = run_pipeline(build_context(question, question.evidence))

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
