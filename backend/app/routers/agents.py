from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentTrackRecord
from ..quant.scoring import brier_score, directional_accuracy, log_score
from ..schemas import AgentLeaderboardRow

router = APIRouter(prefix="/api/agents", tags=["agents"])


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
