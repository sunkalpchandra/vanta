"""Idempotent database seeding.

Seeds the demo questions with evidence, runs the agent pipeline on each,
back-fills a 30-day forecast history (seeded random walk ending at the live
forecast), and generates resolved predictions for the accuracy leaderboard.
"""

import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .data import REFERENCE_EVENTS, SEED_QUESTIONS
from .models import Forecast, Prediction, Question, utcnow
from .quant.bayes import clamp, inv_logit, logit
from .service import create_question, run_and_store_forecast


def seed_if_empty(db: Session) -> bool:
    """Resumable: each seed question and the prediction corpus are checked
    independently, so a startup interrupted mid-seed completes on the next
    boot instead of being blocked forever by a partial database."""
    changed = _seed_questions(db)
    if db.scalar(select(Prediction).limit(1)) is None:
        _seed_resolved_predictions(db)
        changed = True
    return changed


def _seed_questions(db: Session) -> bool:
    existing = set(db.scalars(select(Question.question)).all())
    changed = False
    for spec in SEED_QUESTIONS:
        if spec["question"] in existing:
            continue
        changed = True
        question = create_question(
            db,
            text=spec["question"],
            category=spec["category"],
            horizon_days=spec["horizon_days"],
            market_probability=spec["market_probability"],
            market_volume_usd=spec["volume_usd"],
            market_liquidity=spec["liquidity"],
            evidence=spec["evidence"],
        )
        forecast, _ = run_and_store_forecast(db, question)
        _backfill_history(db, question, forecast)
    db.commit()
    return changed


def _backfill_history(db: Session, question: Question, forecast: Forecast, days: int = 30) -> None:
    """Reverse random walk in log-odds space ending at the live forecast."""
    rng = random.Random(question.id * 7919)
    z = logit(forecast.probability)
    points: list[float] = []
    for _ in range(days):
        z -= rng.gauss(0, 0.12)
        points.append(inv_logit(z))
    points.reverse()
    now = utcnow()
    for i, p in enumerate(points):
        db.add(
            Forecast(
                question_id=question.id,
                probability=round(clamp(p, 0.02, 0.98), 4),
                confidence=forecast.confidence,
                reasoning="(historical snapshot)",
                risk_factors=[],
                timestamp=now - timedelta(days=days - i),
            )
        )


def _seed_resolved_predictions(db: Session) -> None:
    """Resolved track record derived from the reference corpus.

    vanta's simulated estimates are drawn closer to the true outcome than the
    market's — this models the intended edge and gives the leaderboard
    realistic demo numbers. Clearly demo data, deterministic by seed.
    """
    rng = random.Random(1337)
    now = utcnow()
    for text, category, outcome in REFERENCE_EVENTS:
        target = 0.78 if outcome == 1 else 0.22
        market_p = clamp(target + rng.gauss(0, 0.22), 0.03, 0.97)
        vanta_p = clamp(target + rng.gauss(0, 0.13), 0.03, 0.97)
        db.add(
            Prediction(
                question_text=text,
                category=category,
                market_probability=round(market_p, 3),
                vanta_probability=round(vanta_p, 3),
                outcome=outcome,
                resolved_at=now - timedelta(days=rng.randint(3, 180)),
            )
        )
    db.commit()
