from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Forecast, Question
from ..schemas import FeedCard

router = APIRouter(prefix="/api/feed", tags=["feed"])


def latest_forecasts(db: Session) -> list[tuple[Question, Forecast]]:
    """(question, latest forecast) pairs for live (unresolved) questions."""
    questions = db.scalars(select(Question).where(Question.resolved.is_(False))).all()
    pairs: list[tuple[Question, Forecast]] = []
    for q in questions:
        latest = db.scalar(
            select(Forecast)
            .where(Forecast.question_id == q.id)
            .order_by(Forecast.timestamp.desc())
            .limit(1)
        )
        if latest is not None:
            pairs.append((q, latest))
    return pairs


def _headline(question: Question, forecast: Forecast) -> str:
    edge = forecast.probability - question.market_probability
    if edge >= 0.05:
        return f"The market may be underestimating: {question.question.rstrip('?')}"
    if edge <= -0.05:
        return f"The market may be overestimating: {question.question.rstrip('?')}"
    return f"vanta agrees with the market on: {question.question.rstrip('?')}"


@router.get("", response_model=list[FeedCard])
def intelligence_feed(limit: int = 20, db: Session = Depends(get_db)):
    """Discovery cards ranked by |edge| — where vanta most disagrees with markets."""
    pairs = latest_forecasts(db)
    pairs.sort(key=lambda pair: abs(pair[1].probability - pair[0].market_probability), reverse=True)
    return [
        FeedCard(
            question_id=q.id,
            question=q.question,
            category=q.category,
            market_probability=q.market_probability,
            vanta_probability=f.probability,
            confidence=f.confidence,
            edge=round(f.probability - q.market_probability, 4),
            horizon_days=q.horizon_days,
            headline=_headline(q, f),
        )
        for q, f in pairs[:limit]
    ]
