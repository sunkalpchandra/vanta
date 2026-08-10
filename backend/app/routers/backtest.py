"""Real-corpus backtest endpoints — the honest replacement for judging vanta
on the seeded synthetic track record. Everything here is deterministic quant
code over ingested MarketEvents; the LLM is never involved."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..backtest import HORIZONS, run_backtest, summarize
from ..db import get_db
from ..deps import require_operator

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


def _horizon(horizon: int = Query(7, description="7 or 30")) -> int:
    # Literal[7, 30] won't coerce the query string under strict pydantic;
    # validate by hand so callers still get a 422 with a plain message.
    if horizon not in HORIZONS:
        raise HTTPException(status_code=422, detail=f"horizon must be one of {HORIZONS}")
    return horizon


@router.get("/real")
def real_summary(
    horizon: int = Depends(_horizon),
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """vanta vs market vs no-skill baseline on real resolved markets, scored
    leakage-free at T-horizon. 404 until the corpus has been backtested."""
    summary = summarize(db, horizon, category=category)
    if summary["n"] == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no backtest predictions for horizon={horizon}"
                + (f" category={category}" if category else "")
                + "; ingest market events and POST /api/backtest/run first"
            ),
        )
    return summary


@router.get("/real/calibration")
def real_calibration(
    horizon: int = Depends(_horizon),
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Reliability-diagram bins for vanta vs the market over the real corpus.
    Empty list until the corpus has been backtested."""
    return summarize(db, horizon, category=category)["calibration"]


@router.post("/run", dependencies=[Depends(require_operator)])
def run(
    horizon: int = Depends(_horizon),
    limit: int = Query(500, ge=1, le=5000),
    min_volume: float = Query(0.0, ge=0),
    db: Session = Depends(get_db),
):
    """Score up to `limit` not-yet-backtested resolved events, synchronously.
    Idempotent: already-scored events are skipped, so repeated calls walk
    through the corpus in batches."""
    return run_backtest(db, horizon_days=horizon, limit=limit, min_volume=min_volume)
