"""Real-time reasoning chat: ask a question, watch the agent debate stream in.

POST /api/chat answers with Server-Sent Events. A question that fuzzy-matches
an existing one is replayed read-only (nothing stored); a novel question is
created and its first run persisted, mirroring the ask endpoint. Rate limiting
comes for free from the mutation middleware in main.py (POST under /api).

Narration strings inside the streamed reports are upgraded automatically when
an LLM is configured: the agents route their prose through llm.narrate, which
falls back to deterministic template text offline. Probabilities never touch
the LLM either way.
"""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.streaming import stream_pipeline
from ..db import SessionLocal, get_db
from ..deps import require_operator
from ..llm import llm_available
from ..models import AgentReport, Forecast, Question
from ..quant.analogs import tokenize
from ..schemas import Category, EvidenceOut
from ..service import build_context, create_question
from .questions import related as related_questions

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Token-overlap (Jaccard) score above which an incoming question is treated as
# the same question — same tokenizer the analog engine and /related use.
MATCH_THRESHOLD = 0.6


class ChatRequest(BaseModel):
    # Same shape and bounds as AskRequest; category/horizon/market only apply
    # when the question is novel (a matched question keeps its own).
    question: str = Field(min_length=10, max_length=500)
    category: Category = "technology"
    horizon_days: int = Field(default=90, ge=1, le=1000)
    market_probability: float | None = Field(default=None, gt=0, lt=1)


def _best_match(db: Session, text: str) -> tuple[Question | None, float]:
    """Closest existing question by token overlap, or None below threshold."""
    q_tokens = tokenize(text)
    if not q_tokens:
        return None, 0.0
    best, best_score = None, 0.0
    for question in db.scalars(select(Question)).all():
        o_tokens = tokenize(question.question)
        if not o_tokens:
            continue
        score = len(q_tokens & o_tokens) / len(q_tokens | o_tokens)
        if score > best_score:
            best, best_score = question, score
    return (best, best_score) if best_score >= MATCH_THRESHOLD else (None, best_score)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _store_stream_run(db: Session, question: Question, reports: list[dict], forecast: dict) -> None:
    """Persist a streamed run — the same replace-reports/append-forecast
    semantics as service.run_and_store_forecast, applied to the result that
    was already computed while streaming (re-running the pipeline just to
    store it would double the work and any LLM narration)."""
    resolved_now = db.scalar(select(Question.resolved).where(Question.id == question.id))
    if resolved_now:
        return  # resolved while the pipeline streamed; discard, forecasts are frozen
    db.query(AgentReport).filter(AgentReport.question_id == question.id).delete()
    for report in reports:
        db.add(
            AgentReport(
                question_id=question.id,
                agent=report["agent"],
                stance=report["stance"],
                probability=report["probability"],
                argument=report["argument"],
                details=report["details"],
            )
        )
    db.add(
        Forecast(
            question_id=question.id,
            probability=forecast["probability"],
            confidence=forecast["confidence"],
            reasoning=forecast["reasoning"],
            risk_factors=forecast["risk_factors"],
        )
    )
    db.commit()


def _event_stream(question_id: int, status: dict, store: bool) -> Iterator[str]:
    # The request-scoped session is torn down when the handler returns, before
    # this generator runs — so the stream owns its own session.
    with SessionLocal() as db:
        question = db.get(Question, question_id)
        yield _sse("status", status)
        completed = False
        try:
            reports: list[dict] = []
            forecast: dict | None = None
            for kind, data in stream_pipeline(build_context(db, question, question.evidence)):
                if kind == "agent_start":
                    yield _sse("agent_start", {"agent": data})
                elif kind == "agent_report":
                    reports.append(data)
                    yield _sse("agent_report", data)
                else:  # 'forecast' — held back, re-emitted as the closing 'done'
                    forecast = data
            yield _sse(
                "evidence",
                [EvidenceOut.model_validate(e).model_dump(mode="json") for e in question.evidence],
            )
            yield _sse(
                "related",
                [r.model_dump(mode="json") for r in related_questions(question_id=question.id, limit=4, db=db)],
            )
            if store:
                _store_stream_run(db, question, reports, forecast)
            if forecast is not None:
                # The shape ChatConsole renders as the final scorecard.
                yield _sse(
                    "forecast",
                    {
                        "question_id": question.id,
                        "market_probability": question.market_probability,
                        "vanta_probability": forecast["probability"],
                        "confidence": forecast["confidence"],
                        "risk_factors": forecast.get("risk_factors", []),
                        "edge": round(forecast["probability"] - question.market_probability, 4),
                    },
                )
            completed = True
            yield _sse(
                "done",
                {
                    "forecast": forecast,
                    "question_id": question.id,
                    "permalink": f"/questions/{question.id}",
                },
            )
        except Exception:  # headers are already sent; a typed event beats a dead socket
            yield _sse("error", {"detail": "pipeline failed mid-stream", "message": "pipeline failed mid-stream"})
            raise
        finally:
            if store and not completed:
                # Client vanished (GeneratorExit) or the pipeline died before
                # the run was stored: a forecast-less question would fuzzy-match
                # every future re-ask and block a clean retry. Remove it.
                db.rollback()
                orphan = db.get(Question, question_id)
                if orphan is not None and not orphan.forecasts:
                    db.delete(orphan)
                    db.commit()


@router.post("")
def chat(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
):
    """Stream a full forecast run for a question as Server-Sent Events:
    status, per-agent debate, evidence, related questions, final forecast."""
    matched, score = _best_match(db, body.question)
    if matched is not None:
        # Read-only replay of an existing question: nothing is stored, so this
        # branch stays open even when API-key gating is on.
        question_id = matched.id
        status = {
            "mode": "matched",
            "matched": True,  # ChatConsole reads the boolean
            "question_id": matched.id,
            "question": matched.question,
            "similarity": round(score, 3),
            "llm_narratives": llm_available(),
        }
        store = False
    else:
        # Deliberately NOT a route-level Depends(require_operator): that would
        # also gate the matched branch. Only minting a new question is a
        # mutation, so the creation branch runs the same operator check
        # manually — identical 401 semantics to the ask endpoint.
        require_operator(request, db=db, x_api_key=x_api_key)
        question = create_question(
            db,
            text=body.question,
            category=body.category,
            horizon_days=body.horizon_days,
            market_probability=body.market_probability,
        )
        question_id = question.id
        status = {
            "mode": "created",
            "matched": False,
            "question_id": question.id,
            "question": question.question,
            "similarity": None,
            "llm_narratives": llm_available(),
        }
        store = True
    return StreamingResponse(
        _event_stream(question_id, status, store),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
