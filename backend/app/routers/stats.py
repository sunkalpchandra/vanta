from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents.historian import CATEGORY_BASE_RATES
from ..db import get_db
from ..llm import llm_available
from ..models import Prediction, Question
from ..quant.scoring import brier_score, directional_accuracy, log_score, murphy_decomposition
from ..schemas import CategoryOut, StatsOut
from .feed import latest_forecasts

router = APIRouter(tags=["stats"])


@router.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    """One-glance system state: live coverage, resolved track record, edge."""
    predictions = db.scalars(select(Prediction)).all()
    vanta_pairs = [(p.vanta_probability, p.outcome) for p in predictions]
    market_pairs = [(p.market_probability, p.outcome) for p in predictions]
    pairs = latest_forecasts(db)
    edges = [abs(f.probability - q.market_probability) for q, f in pairs]
    murphy = murphy_decomposition(vanta_pairs) if vanta_pairs else None
    return StatsOut(
        n_live_questions=len(pairs),
        n_resolved=len(predictions),
        vanta_accuracy=round(directional_accuracy(vanta_pairs), 4) if vanta_pairs else None,
        market_accuracy=round(directional_accuracy(market_pairs), 4) if market_pairs else None,
        vanta_brier=round(brier_score(vanta_pairs), 4) if vanta_pairs else None,
        market_brier=round(brier_score(market_pairs), 4) if market_pairs else None,
        vanta_log_score=round(log_score(vanta_pairs), 4) if vanta_pairs else None,
        market_log_score=round(log_score(market_pairs), 4) if market_pairs else None,
        vanta_reliability=murphy.reliability if murphy else None,
        vanta_resolution=murphy.resolution if murphy else None,
        outcome_uncertainty=murphy.uncertainty if murphy else None,
        avg_abs_edge=round(sum(edges) / len(edges), 4) if edges else None,
        llm_narratives=llm_available(),
    )


@router.get("/api/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    """Coverage per category with the historian's long-run base rates."""
    live_counts = dict(
        db.execute(
            select(Question.category, func.count())
            .where(Question.resolved.is_(False))
            .group_by(Question.category)
        ).all()
    )
    resolved_counts = dict(
        db.execute(select(Prediction.category, func.count()).group_by(Prediction.category)).all()
    )
    names = sorted(set(CATEGORY_BASE_RATES) | set(live_counts) | set(resolved_counts))
    return [
        CategoryOut(
            category=name,
            base_rate=CATEGORY_BASE_RATES.get(name, 0.42),
            n_live_questions=live_counts.get(name, 0),
            n_resolved=resolved_counts.get(name, 0),
        )
        for name in names
    ]
