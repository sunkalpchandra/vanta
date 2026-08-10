from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Prediction
from ..quant.scoring import calibration_bins
from ..schemas import CalibrationBinOut, LeaderboardRow

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


@router.get("/calibration", response_model=list[CalibrationBinOut])
def calibration(db: Session = Depends(get_db)):
    """Reliability-diagram bins for vanta vs the market over resolved questions.
    A calibrated forecaster's observed rates track its predicted rates."""
    predictions = db.scalars(select(Prediction)).all()
    vanta = calibration_bins([(p.vanta_probability, p.outcome) for p in predictions])
    market = calibration_bins([(p.market_probability, p.outcome) for p in predictions])
    return [
        CalibrationBinOut(
            mid=v.mid,
            vanta_mean_predicted=v.mean_predicted,
            vanta_observed_rate=v.observed_rate,
            vanta_count=v.count,
            market_mean_predicted=m.mean_predicted,
            market_observed_rate=m.observed_rate,
            market_count=m.count,
        )
        for v, m in zip(vanta, market, strict=True)
    ]
