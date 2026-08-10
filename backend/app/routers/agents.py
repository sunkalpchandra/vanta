from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentTrackRecord, Question
from ..quant.scoring import brier_score, calibration_bins, directional_accuracy, log_score
from ..schemas import AgentLeaderboardRow

router = APIRouter(prefix="/api/agents", tags=["agents"])

KNOWN_AGENTS = {"research", "quant", "market", "sentiment", "historian", "synthesis"}


@router.get("/leaderboard", response_model=list[AgentLeaderboardRow])
def agent_leaderboard(db: Session = Depends(get_db)):
    """The internal forecaster competition: each agent's frozen calls scored
    against resolved outcomes. Only live-resolved questions count — the
    seeded reference corpus predates the agent pipeline."""
    by_agent: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for record in db.scalars(select(AgentTrackRecord)).all():
        by_agent[record.agent].append((record.probability, record.outcome))
    rows = [
        AgentLeaderboardRow(
            agent=agent,
            n_resolved=len(pairs),
            accuracy=round(directional_accuracy(pairs), 4),
            brier=round(brier_score(pairs), 4),
            log_score=round(log_score(pairs), 4),
        )
        for agent, pairs in by_agent.items()
    ]
    rows.sort(key=lambda r: r.brier)
    return rows


@router.get("/{agent_name}/calibration")
def agent_calibration(agent_name: str, db: Session = Depends(get_db)):
    """Reliability bins for one agent's frozen calls."""
    if agent_name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail="unknown agent")
    pairs = [
        (record.probability, record.outcome)
        for record in db.scalars(
            select(AgentTrackRecord).where(AgentTrackRecord.agent == agent_name)
        ).all()
    ]
    if not pairs:
        return []
    return [
        {
            "mid": b.mid,
            "mean_predicted": b.mean_predicted,
            "observed_rate": b.observed_rate,
            "count": b.count,
        }
        for b in calibration_bins(pairs)
    ]


@router.get("/{agent_name}/records")
def agent_records(agent_name: str, db: Session = Depends(get_db)):
    """One agent's frozen calls against outcomes — the receipts behind its
    leaderboard row."""
    if agent_name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail="unknown agent")
    rows = db.execute(
        select(AgentTrackRecord, Question.question)
        .join(Question, Question.id == AgentTrackRecord.question_id)
        .where(AgentTrackRecord.agent == agent_name)
        .order_by(AgentTrackRecord.resolved_at.desc())
    ).all()
    return [
        {
            "question_id": record.question_id,
            "question": question_text,
            "probability": record.probability,
            "outcome": record.outcome,
            "abs_error": round(abs(record.probability - record.outcome), 4),
        }
        for record, question_text in rows
    ]
