from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Evidence, Forecast, MarketSnapshot, Question
from ..quant.analogs import tokenize
from ..schemas import (
    AskRequest,
    EvidenceIn,
    ForecastOut,
    HistoryPoint,
    MarketPoint,
    MarketUpdateRequest,
    QuestionDetail,
    QuestionOut,
    RelatedQuestion,
    ResolveRequest,
)
from ..service import (
    ResolutionError,
    create_question,
    evidence_sensitivity,
    record_market_price,
    resolve_question,
    run_and_store_forecast,
)
from .brief import invalidate_brief_cache

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
def list_questions(
    category: str | None = None,
    resolved: bool | None = None,
    q: str | None = None,
    limit: int | None = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Question).order_by(Question.created_at.desc())
    if category:
        stmt = stmt.where(Question.category == category)
    if resolved is not None:
        stmt = stmt.where(Question.resolved.is_(resolved))
    if q:
        stmt = stmt.where(Question.question.ilike(f"%{q}%"))
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
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
    try:
        run_and_store_forecast(db, question)
    except ResolutionError as exc:  # resolved while the pipeline ran
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    invalidate_brief_cache()  # the brief must stop pitching a settled question
    return _detail(db, question)


@router.post("/{question_id}/evidence", response_model=QuestionDetail, status_code=201)
def add_evidence(question_id: int, body: EvidenceIn, db: Session = Depends(get_db)):
    """Ingest a new signal for a question and re-run the agent pipeline so the
    forecast reflects it immediately."""
    question = _get_question_or_404(db, question_id)
    if question.resolved:
        raise HTTPException(status_code=409, detail="question is resolved; evidence is frozen")
    db.add(
        Evidence(
            question_id=question.id,
            source=body.source,
            summary=body.summary,
            sentiment=body.sentiment,
            impact=body.impact,
        )
    )
    db.commit()
    db.refresh(question)
    try:
        run_and_store_forecast(db, question)
    except ResolutionError as exc:  # resolved while the pipeline ran
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _detail(db, question)


@router.get("/{question_id}/related", response_model=list[RelatedQuestion])
def related(question_id: int, limit: int = Query(4, ge=1, le=10), db: Session = Depends(get_db)):
    """Topically similar questions by token overlap (category counts a little)."""
    question = _get_question_or_404(db, question_id)
    q_tokens = tokenize(question.question)
    if not q_tokens:
        return []
    scored: list[RelatedQuestion] = []
    for other in db.scalars(select(Question).where(Question.id != question_id)).all():
        o_tokens = tokenize(other.question)
        if not o_tokens:
            continue
        overlap = len(q_tokens & o_tokens) / len(q_tokens | o_tokens)
        score = overlap + (0.05 if other.category == question.category else 0.0)
        if overlap > 0 and score >= 0.12:
            scored.append(
                RelatedQuestion(
                    id=other.id,
                    question=other.question,
                    category=other.category,
                    similarity=round(score, 3),
                    resolved=other.resolved,
                )
            )
    scored.sort(key=lambda r: r.similarity, reverse=True)
    return scored[:limit]


@router.get("/{question_id}/sensitivity")
def sensitivity(question_id: int, db: Session = Depends(get_db)):
    """Leave-one-out evidence importance — which signals actually move this
    forecast, and by how much."""
    question = _get_question_or_404(db, question_id)
    return {"items": evidence_sensitivity(db, question)}


@router.post("/{question_id}/market", response_model=QuestionDetail)
def update_market_price(question_id: int, body: MarketUpdateRequest, db: Session = Depends(get_db)):
    """Ingest a new market price. Doesn't re-run the pipeline by itself —
    call /refresh afterwards if the move warrants a re-forecast."""
    question = _get_question_or_404(db, question_id)
    try:
        record_market_price(db, question, body.probability)
    except ResolutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _detail(db, question)


@router.get("/{question_id}/market-history", response_model=list[MarketPoint])
def market_history(question_id: int, db: Session = Depends(get_db)):
    _get_question_or_404(db, question_id)
    rows = db.scalars(
        select(MarketSnapshot)
        .where(MarketSnapshot.question_id == question_id)
        .order_by(MarketSnapshot.timestamp.asc(), MarketSnapshot.id.asc())
    ).all()
    return [MarketPoint(timestamp=s.timestamp, probability=s.probability) for s in rows]


@router.get("/{question_id}/analogs")
def analogs(question_id: int, db: Session = Depends(get_db)):
    """The quant agent's historical analog matches from the latest run."""
    question = _get_question_or_404(db, question_id)
    quant = next((r for r in question.agent_reports if r.agent == "quant"), None)
    if quant is None:
        return {"analogs": [], "hit_rate": None, "n_analogs": 0}
    return {
        "analogs": quant.details.get("analogs", []),
        "hit_rate": quant.details.get("hit_rate"),
        "n_analogs": quant.details.get("n_analogs", 0),
    }


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
