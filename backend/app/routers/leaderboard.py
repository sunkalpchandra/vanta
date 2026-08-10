from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Prediction
from ..schemas import LeaderboardRow

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


def _accuracy(rows: list[Prediction], attr: str) -> float:
    hits = sum(1 for r in rows if (getattr(r, attr) >= 0.5) == bool(r.outcome))
    return hits / len(rows)


def _brier(rows: list[Prediction], attr: str) -> float:
    return sum((getattr(r, attr) - r.outcome) ** 2 for r in rows) / len(rows)


@router.get("", response_model=list[LeaderboardRow])
def leaderboard(db: Session = Depends(get_db)):
    """vanta vs market accuracy and Brier score by category, on resolved questions."""
    by_category: dict[str, list[Prediction]] = defaultdict(list)
    for row in db.scalars(select(Prediction)).all():
        by_category[row.category].append(row)

    out = [
        LeaderboardRow(
            category=category,
            n_resolved=len(rows),
            vanta_accuracy=round(_accuracy(rows, "vanta_probability"), 3),
            market_accuracy=round(_accuracy(rows, "market_probability"), 3),
            vanta_brier=round(_brier(rows, "vanta_probability"), 4),
            market_brier=round(_brier(rows, "market_probability"), 4),
        )
        for category, rows in by_category.items()
        if rows
    ]
    out.sort(key=lambda r: r.vanta_accuracy, reverse=True)
    return out
