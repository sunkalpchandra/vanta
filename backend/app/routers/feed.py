from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Forecast, Question, utcnow
from ..schemas import FeedCard, MoverCard

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


@router.get("/movers", response_model=list[MoverCard])
def movers(
    days: int = Query(3, ge=1, le=30),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Where vanta's own probability moved most over the window — the
    questions whose evidence picture is changing fastest."""
    cutoff = utcnow() - timedelta(days=days)
    cards: list[MoverCard] = []
    for question, latest in latest_forecasts(db):
        previous = db.scalar(
            select(Forecast)
            .where(Forecast.question_id == question.id, Forecast.timestamp <= cutoff)
            .order_by(Forecast.timestamp.desc())
            .limit(1)
        )
        if previous is None:
            continue  # question younger than the window
        delta = latest.probability - previous.probability
        cards.append(
            MoverCard(
                question_id=question.id,
                question=question.question,
                category=question.category,
                current=latest.probability,
                previous=previous.probability,
                delta=round(delta, 4),
                window_days=days,
            )
        )
    cards.sort(key=lambda c: abs(c.delta), reverse=True)
    return cards[:limit]


SORT_KEYS = {
    "edge": lambda q, f: abs(f.probability - q.market_probability),
    "confidence": lambda q, f: f.confidence,
    "volume": lambda q, f: q.market_volume_usd,
}


@router.get("", response_model=list[FeedCard])
def intelligence_feed(
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("edge", pattern="^(edge|confidence|volume)$"),
    db: Session = Depends(get_db),
):
    """Discovery cards for live questions. Default ranking: |edge| — where
    vanta most disagrees with markets. Also sortable by confidence or volume."""
    pairs = latest_forecasts(db)
    key = SORT_KEYS[sort]
    pairs.sort(key=lambda pair: key(pair[0], pair[1]), reverse=True)
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
