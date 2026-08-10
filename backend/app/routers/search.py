from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Prediction, Question

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Unified search across live questions and the resolved track record."""
    needle = f"%{q}%"
    questions = db.scalars(
        select(Question).where(Question.question.ilike(needle)).order_by(Question.created_at.desc()).limit(limit)
    ).all()
    predictions = db.scalars(
        select(Prediction)
        .where(Prediction.question_text.ilike(needle), Prediction.question_id.is_(None))
        .order_by(Prediction.resolved_at.desc())
        .limit(limit)
    ).all()
    return {
        "questions": [
            {"id": item.id, "question": item.question, "category": item.category, "resolved": item.resolved}
            for item in questions
        ],
        # Corpus-only rows (question_id null) — linked rows already surface above.
        "archive": [
            {"question": item.question_text, "category": item.category, "outcome": item.outcome}
            for item in predictions
        ],
    }
