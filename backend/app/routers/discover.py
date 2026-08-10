from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..discovery import discover, pending_candidates
from ..schemas import DiscoveredQuestion, QuestionOut

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.get("/candidates")
def candidates(db: Session = Depends(get_db)):
    """Preview watchlist questions not yet covered by the question base."""
    return [
        {"question": c.question, "category": c.category, "horizon_days": c.horizon_days, "rationale": c.rationale}
        for c in pending_candidates(db)
    ]


@router.post("", response_model=list[DiscoveredQuestion], status_code=201)
def run_discovery(count: int = Query(3, ge=1, le=5), db: Session = Depends(get_db)):
    """Autonomous research mode: mint new questions from uncovered watchlist
    signals and forecast each with the full agent pipeline."""
    return [
        DiscoveredQuestion(question=QuestionOut.model_validate(q), rationale=c.rationale)
        for q, c in discover(db, count)
    ]
