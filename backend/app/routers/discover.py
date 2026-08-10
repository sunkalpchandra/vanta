from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..discovery import discover, pending_candidates
from ..models import WatchlistItem
from ..schemas import DiscoveredQuestion, QuestionOut, WatchlistIn

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.post("/watchlist", status_code=201)
def add_watchlist_item(body: WatchlistIn, db: Session = Depends(get_db)):
    """Point autonomous research at a signal worth watching."""
    exists = db.scalar(select(WatchlistItem).where(WatchlistItem.question == body.question))
    if exists is not None:
        raise HTTPException(status_code=409, detail="already on the watchlist")
    item = WatchlistItem(
        question=body.question,
        category=body.category,
        horizon_days=body.horizon_days,
        rationale=body.rationale,
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "question": item.question}


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
