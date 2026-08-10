import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Prediction
from ..quant.scoring import calibration_bins
from ..schemas import CalibrationBinOut, LeaderboardRow, PredictionOut

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


@router.get("/predictions", response_model=list[PredictionOut])
def predictions(
    category: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """The resolved track record, newest first — every settled call vanta has made."""
    stmt = select(Prediction).order_by(Prediction.resolved_at.desc()).limit(limit)
    if category:
        stmt = stmt.where(Prediction.category == category)
    return db.scalars(stmt).all()


@router.get("/predictions.csv")
def predictions_csv(db: Session = Depends(get_db)):
    """The resolved track record as CSV — for spreadsheets and notebooks."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["question_id", "question", "category", "market_probability", "vanta_probability", "outcome", "resolved_at"]
    )
    for p in db.scalars(select(Prediction).order_by(Prediction.resolved_at.desc())).all():
        writer.writerow(
            [
                p.question_id or "",
                p.question_text,
                p.category,
                p.market_probability,
                p.vanta_probability,
                p.outcome,
                p.resolved_at.isoformat(),
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vanta-track-record.csv"'},
    )


@router.get("/calibration", response_model=list[CalibrationBinOut])
def calibration(category: str | None = None, db: Session = Depends(get_db)):
    """Reliability-diagram bins for vanta vs the market over resolved questions.
    A calibrated forecaster's observed rates track its predicted rates."""
    stmt = select(Prediction)
    if category:
        stmt = stmt.where(Prediction.category == category)
    predictions = db.scalars(stmt).all()
    if not predictions:
        return []
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
