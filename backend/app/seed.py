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
from .models import Forecast, MarketSnapshot, Prediction, Question, utcnow
from .quant.bayes import clamp, inv_logit, logit
from .service import ResolutionError, create_question, resolve_question, run_and_store_forecast

# Two seeded questions resolve at seed time so the archive, the resolved
# filters, and the agent leaderboard have live-path content in the demo.
# Outcomes are fixtures, chosen to match the corpus's own base rates.
BACKFILL_REASONING = "(historical snapshot)"

DEMO_RESOLUTIONS: list[tuple[str, bool]] = [
    ("Will the favorite win the NBA championship this season?", False),
    ("Will SpaceX land Starship's upper stage back at the launch site this year?", True),
]


def seed_if_empty(db: Session) -> bool:
    """Resumable: each seed question and the prediction corpus are checked
    independently, so a startup interrupted mid-seed completes on the next
    boot instead of being blocked forever by a partial database."""
    changed = _seed_questions(db)
    if db.scalar(select(Prediction).limit(1)) is None:
        _seed_resolved_predictions(db)
        changed = True
    changed = _seed_demo_resolutions(db) or changed
    changed = _seed_demo_markets(db) or changed
    return changed


def _seed_demo_markets(db: Session) -> bool:
    """A small set of active demo MarketEvents + price ticks so the play-money
    trading surface and its /markets/{id} pages exist in the static export
    (which bakes from a fresh seed, before any live venue sync). Clearly demo
    data — deterministic, labeled 'demo' as the source."""
    from .models import MarketEvent, PriceTick

    if db.scalar(select(MarketEvent).where(MarketEvent.source == "demo").limit(1)) is not None:
        return False
    rng = random.Random(90210)
    now = utcnow()
    demos = [
        ("Will a demo market resolve YES by year end?", "technology", 0.62),
        ("Will the sample index close higher this quarter?", "finance", 0.48),
        ("Will the reference team win the demo series?", "sports", 0.55),
        ("Will the demo protocol ship its upgrade on time?", "crypto", 0.34),
        ("Will the placeholder policy pass this session?", "politics", 0.41),
        ("Will the demo mission launch before the window closes?", "science", 0.71),
    ]
    for i, (question, category, price) in enumerate(demos):
        event = MarketEvent(
            source="demo",
            source_id=f"demo-{i}",
            question=question,
            category=category,
            active=True,
            yes_price=price,
            outcome=None,
            volume_usd=float(50_000 + i * 25_000),
            close_time=now + timedelta(days=30 + i * 10),
            last_synced=now,
        )
        db.add(event)
        db.flush()
        # A deterministic 20-day reverse walk of ticks so the detail chart has
        # a real series in the demo.
        walk = price
        for d in range(20, 0, -1):
            walk = clamp(walk + rng.gauss(0, 0.03), 0.05, 0.95)
            db.add(
                PriceTick(
                    event_id=event.id,
                    yes_price=round(walk, 4),
                    timestamp=now - timedelta(days=d),
                )
            )
        db.add(PriceTick(event_id=event.id, yes_price=price, timestamp=now))
    db.commit()

    # A demo trader with a couple of trades, so the trader leaderboard and the
    # /traders/{name} pages exist in the static export (which bakes from a fresh
    # seed). Without this the dynamic route has zero params and output:export
    # fails the build. Clearly a demo account.
    from .models import User
    from .trading import execute_trade

    if db.scalar(select(User).where(User.email == "demo-trader@demo.vanta")) is None:
        bot = User(email="demo-trader@demo.vanta", api_key="vk_demo_trader_readonly")
        db.add(bot)
        db.commit()
        demo_events = db.scalars(select(MarketEvent).where(MarketEvent.source == "demo")).all()
        for event in demo_events[:3]:
            try:
                execute_trade(db, bot, event, "yes", "buy", 25)
            except Exception:  # never let a demo trade block startup
                continue
    return True


def _seed_demo_resolutions(db: Session) -> bool:
    changed = False
    for text, outcome in DEMO_RESOLUTIONS:
        question = db.scalar(select(Question).where(Question.question == text))
        if question is None or question.resolved:
            continue
        try:
            resolve_question(db, question, outcome)
            changed = True
        except ResolutionError:  # e.g. no forecast yet — leave it live
            continue
    return changed


def _seed_questions(db: Session) -> bool:
    changed = False
    for spec in SEED_QUESTIONS:
        question = db.scalar(select(Question).where(Question.question == spec["question"]))
        if question is None:
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
        elif _has_forecast(db, question):
            if not _has_market_history(db, question):
                _backfill_market_history(db, question)  # upgraded/interrupted DBs
                changed = True
            if not _has_backfill(db, question):
                # Crash after the live-forecast commit but before the backfill
                # commit: finish the vanta side too.
                live = db.scalar(
                    select(Forecast)
                    .where(Forecast.question_id == question.id)
                    .order_by(Forecast.timestamp.desc(), Forecast.id.desc())
                    .limit(1)
                )
                _backfill_history(db, question, live)
                _spread_evidence_dates(db, question)
                changed = True
            db.commit()
            continue  # fully seeded on an earlier boot
        else:
            # Crash landed between the question commit and the forecast
            # commit on a previous boot — finish the job, don't skip it.
            changed = True
        forecast, _ = run_and_store_forecast(db, question)
        _backfill_history(db, question, forecast)
        _backfill_market_history(db, question)
        _spread_evidence_dates(db, question)
        db.commit()  # per-question: shrink the crash window to one pipeline run
    return changed


def _spread_evidence_dates(db: Session, question: Question, max_age_days: int = 25) -> None:
    """Seeded evidence didn't all arrive today: spread arrival dates over the
    past weeks (deterministic per question) so chart markers tell a story."""
    rng = random.Random(question.id * 31337 + 11)
    now = utcnow()
    for evidence in question.evidence:
        evidence.created_at = now - timedelta(days=rng.randint(1, max_age_days), hours=rng.randint(0, 23))


def _has_forecast(db: Session, question: Question) -> bool:
    return db.scalar(select(Forecast).where(Forecast.question_id == question.id).limit(1)) is not None


def _has_backfill(db: Session, question: Question) -> bool:
    return (
        db.scalar(
            select(Forecast)
            .where(Forecast.question_id == question.id, Forecast.reasoning == BACKFILL_REASONING)
            .limit(1)
        )
        is not None
    )


def _has_market_history(db: Session, question: Question) -> bool:
    return (
        db.scalar(select(MarketSnapshot).where(MarketSnapshot.question_id == question.id).limit(1))
        is not None
    )


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
                reasoning=BACKFILL_REASONING,
                risk_factors=[],
                timestamp=now - timedelta(days=days - i),
            )
        )


def _backfill_market_history(db: Session, question: Question, days: int = 30) -> None:
    """Reverse random walk ending at the question's current market price —
    the market side of the market-vs-vanta chart. Different RNG stream than
    the forecast walk so the two series genuinely diverge."""
    if _has_market_history(db, question):
        return  # idempotent across interrupted boots
    rng = random.Random(question.id * 104729 + 7)
    z = logit(question.market_probability)
    points: list[float] = []
    for _ in range(days):
        z -= rng.gauss(0, 0.10)
        points.append(inv_logit(z))
    points.reverse()
    now = utcnow()
    for i, p in enumerate(points):
        db.add(
            MarketSnapshot(
                question_id=question.id,
                probability=round(clamp(p, 0.02, 0.98), 4),
                timestamp=now - timedelta(days=days - i),
            )
        )
    db.add(MarketSnapshot(question_id=question.id, probability=question.market_probability, timestamp=now))


def _seed_resolved_predictions(db: Session) -> None:
    """Resolved track record derived from the reference corpus.

    vanta's simulated estimate derives from the MARKET signal (shrunk toward
    the prior, plus independent noise) — never from the outcome. An earlier
    version noised vanta around the known outcome, which rigged the synthetic
    leaderboard to ~100% accuracy. The synthetic corpus exists to exercise
    the surfaces and deliberately claims NO edge; the only real accuracy
    numbers come from the market_events backtest.
    """
    rng = random.Random(1337)
    now = utcnow()
    for text, category, outcome in REFERENCE_EVENTS:
        target = 0.78 if outcome == 1 else 0.22
        market_p = clamp(target + rng.gauss(0, 0.22), 0.03, 0.97)
        vanta_p = clamp(0.85 * market_p + 0.15 * 0.5 + rng.gauss(0, 0.06), 0.03, 0.97)
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
