from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Forecast, Question
from ..schemas import AskRequest, ForecastOut, HistoryPoint, QuestionDetail, QuestionOut, ResolveRequest
from ..service import ResolutionError, create_question, resolve_question, run_and_store_forecast

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _get_question_or_404(db: Session, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="question not found")
    return question


def _latest_forecast(db: Session, question_id: int) -> Forecast | None:
    return db.scalar(
        select(Forecast)
        .where(Forecast.question_id == question_id)
        .order_by(Forecast.timestamp.desc())
        .limit(1)
    )


@router.get("", response_model=list[QuestionOut])
def list_questions(category: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Question).order_by(Question.created_at.desc())
    if category:
        stmt = stmt.where(Question.category == category)
    return db.scalars(stmt).all()


@router.post("", response_model=QuestionDetail, status_code=201)
def ask_question(body: AskRequest, db: Session = Depends(get_db)):
    """User-submitted question: create it and run the full agent pipeline."""
    question = create_question(
        db,
        text=body.question,
        category=body.category,
        horizon_days=body.horizon_days,
        market_probability=body.market_probability,
    )
    run_and_store_forecast(db, question)
    return _detail(db, question)


@router.get("/{question_id}", response_model=QuestionDetail)
def get_question(question_id: int, db: Session = Depends(get_db)):
    return _detail(db, _get_question_or_404(db, question_id))


@router.post("/{question_id}/refresh", response_model=QuestionDetail)
def refresh_forecast(question_id: int, db: Session = Depends(get_db)):
    question = _get_question_or_404(db, question_id)
    if question.resolved:
        raise HTTPException(status_code=409, detail="question is resolved; forecasts are frozen")
    run_and_store_forecast(db, question)
    return _detail(db, question)


@router.post("/{question_id}/resolve", response_model=QuestionDetail)
def resolve(question_id: int, body: ResolveRequest, db: Session = Depends(get_db)):
    """Settle the question against reality. Freezes forecasting and writes the
    resolved prediction that feeds the accuracy leaderboard."""
    question = _get_question_or_404(db, question_id)
    try:
        resolve_question(db, question, body.outcome)
    except ResolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _detail(db, question)


@router.get("/{question_id}/history", response_model=list[HistoryPoint])
def forecast_history(question_id: int, db: Session = Depends(get_db)):
    _get_question_or_404(db, question_id)
    rows = db.scalars(
        select(Forecast).where(Forecast.question_id == question_id).order_by(Forecast.timestamp.asc())
    ).all()
    return [HistoryPoint(timestamp=f.timestamp, probability=f.probability) for f in rows]


def _detail(db: Session, question: Question) -> QuestionDetail:
    detail = QuestionDetail.model_validate(question)
    latest = _latest_forecast(db, question.id)
    detail.latest_forecast = ForecastOut.model_validate(latest) if latest else None
    detail.evidence = [e for e in question.evidence]
    detail.agent_reports = [r for r in question.agent_reports]
    return detail
