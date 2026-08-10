from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import utcnow
from ..schemas import AlertItem
from .feed import latest_forecasts, previous_forecasts

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertItem])
def alerts(
    days: int = Query(3, ge=1, le=30),
    min_move: float = Query(0.05, gt=0, lt=1),
    min_edge: float = Query(0.15, gt=0, lt=1),
    db: Session = Depends(get_db),
):
    """Attention-worthy state, derived not stored: live questions whose vanta
    probability moved ≥ min_move inside the window, or whose |edge| ≥ min_edge
    right now. One alert per question — the larger signal wins."""
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=days)
    previous_by_question = previous_forecasts(db, cutoff)
    items: list[AlertItem] = []
    for question, latest in latest_forecasts(db):
        edge = latest.probability - question.market_probability
        previous = previous_by_question.get(question.id)
        move = (
            latest.probability - previous.probability
            if previous is not None and previous.id != latest.id
            else 0.0
        )
        candidates: list[AlertItem] = []
        if abs(move) >= min_move:
            candidates.append(
                AlertItem(
                    kind="move",
                    question_id=question.id,
                    question=question.question,
                    category=question.category,
                    value=round(move, 4),
                    detail=f"vanta moved {move:+.0%} in {days}d",
                )
            )
        if abs(edge) >= min_edge:
            candidates.append(
                AlertItem(
                    kind="edge",
                    question_id=question.id,
                    question=question.question,
                    category=question.category,
                    value=round(edge, 4),
                    detail=f"{abs(edge):.0%} disagreement with the market",
                )
            )
        if candidates:
            items.append(max(candidates, key=lambda a: abs(a.value)))
    items.sort(key=lambda a: abs(a.value), reverse=True)
    return items
