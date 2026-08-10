"""Leakage-free backtest of the agent pipeline over the real ingested corpus.

This replaces the seeded synthetic track record — whose accuracy was a
property of the seed — with a check against real markets. For every resolved
MarketEvent with a captured pre-close price, the pipeline is re-run on exactly
what it would have known h days before close: the market price at T-h, the
category, and a base rate learned from OTHER events' outcomes. No evidence
survives from the past, so none is provided — the pipeline leans on priors and
abstains where it must, which is the honest condition. Narratives are off, so
no LLM call can occur and every number is deterministic. vanta and the market
are then scored against the same outcomes from identical information.
"""

import statistics

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .agents.base import QuestionContext
from .agents.historian import base_rate_for
from .agents.orchestrator import run_pipeline
from .models import BacktestPrediction, MarketEvent
from .quant.scoring import brier_score, calibration_bins, directional_accuracy, log_score

# Same phantom-resolution shrinkage as service.learned_base_rate: the static
# prior acts as 20 resolutions, so observed rates take over gradually.
PSEUDO_COUNT = 20.0
COMMIT_BATCH = 500
HORIZONS = (7, 30)


def _price_column(horizon_days: int):
    if horizon_days not in HORIZONS:
        raise ValueError(f"horizon_days must be one of {HORIZONS}")
    return MarketEvent.price_7d if horizon_days == 7 else MarketEvent.price_30d


def _price_of(event: MarketEvent, horizon_days: int) -> float | None:
    return event.price_7d if horizon_days == 7 else event.price_30d


def liquidity_for_volume(volume_usd: float) -> str:
    """Deterministic liquidity tag from traded volume. The live corpus carries
    a curator-set tag; the historical corpus only has volume, so the tag is
    derived the same way for every event."""
    if volume_usd >= 1_000_000:
        return "high"
    if volume_usd >= 100_000:
        return "medium"
    return "low"


def category_outcome_counts(db: Session) -> dict[str, tuple[int, int]]:
    """(n_resolved, n_yes) per category over the resolved MarketEvent corpus."""
    rows = db.execute(
        select(MarketEvent.category, func.count(), func.sum(MarketEvent.outcome))
        .where(MarketEvent.outcome.is_not(None))
        .group_by(MarketEvent.category)
    ).all()
    return {category: (int(n), int(yes or 0)) for category, n, yes in rows}


def leave_one_out_base_rate(counts: dict[str, tuple[int, int]], category: str, own_outcome: int) -> float:
    """Category base rate learned from OTHER events only: the event's own
    outcome is subtracted before blending, so no event informs its own prior.
    Mirrors service.learned_base_rate's pseudo-count shrinkage."""
    static = base_rate_for(category)
    n, yes = counts.get(category, (0, 0))
    n -= 1
    yes -= own_outcome
    if n <= 0:
        return static
    return (static * PSEUDO_COUNT + yes) / (PSEUDO_COUNT + n)


def context_for(event: MarketEvent, horizon_days: int, base_rate: float) -> QuestionContext:
    """The context the live pipeline would have seen at T-h. Evidence stays
    empty: none was captured back then, and fabricating any would let the
    present leak into the past."""
    volume = event.volume_usd or 0.0
    return QuestionContext(
        question=event.question,
        category=event.category,
        horizon_days=horizon_days,
        market_probability=_price_of(event, horizon_days),
        market_volume_usd=volume,
        market_liquidity=liquidity_for_volume(volume),
        evidence=[],
        base_rate=round(base_rate, 4),
        narratives=False,  # numbers only — the LLM never touches a backtest
    )


def run_backtest(
    db: Session,
    horizon_days: int = 7,
    limit: int | None = None,
    min_volume: float = 0.0,
) -> dict:
    """Score every eligible resolved event not yet backtested at this horizon.

    Eligible: outcome known, pre-close price captured, at least min_volume
    traded. Already-scored events are skipped (the unique index on
    (event_id, horizon_days) backstops concurrent runs), so re-running is
    idempotent. Commits every COMMIT_BATCH rows so a large corpus can't hold
    one transaction open for minutes.
    """
    price_col = _price_column(horizon_days)
    already_scored = select(BacktestPrediction.event_id).where(
        BacktestPrediction.horizon_days == horizon_days
    )
    stmt = (
        select(MarketEvent)
        .where(
            MarketEvent.outcome.is_not(None),
            price_col.is_not(None),
            MarketEvent.id.not_in(already_scored),
        )
        .order_by(MarketEvent.id)
    )
    if min_volume > 0:
        stmt = stmt.where(MarketEvent.volume_usd >= min_volume)
    if limit is not None:
        stmt = stmt.limit(limit)

    counts = category_outcome_counts(db)
    # Snapshot (id, context, outcome) tuples before any commit: commits expire
    # ORM instances, and re-reading them mid-run would cost a query per event.
    todo = [
        (event.id, context_for(event, horizon_days, leave_one_out_base_rate(counts, event.category, event.outcome)),
         event.outcome)
        for event in db.scalars(stmt).all()
    ]

    scored = 0
    pending = 0
    for event_id, ctx, outcome in todo:
        result = run_pipeline(ctx)
        db.add(
            BacktestPrediction(
                event_id=event_id,
                horizon_days=horizon_days,
                # ctx.market_probability IS the stored market side: both
                # forecasters are scored on identical inputs by construction.
                market_probability=ctx.market_probability,
                vanta_probability=result.probability,
                outcome=outcome,
            )
        )
        pending += 1
        if pending >= COMMIT_BATCH:
            db.commit()
            scored += pending
            pending = 0
    if pending:
        db.commit()
        scored += pending

    total = db.scalar(
        select(func.count())
        .select_from(BacktestPrediction)
        .where(BacktestPrediction.horizon_days == horizon_days)
    )
    return {
        "horizon_days": horizon_days,
        "n_scored": scored,
        "n_already_scored": (total or 0) - scored,
        "n_total": total or 0,
        "min_volume": min_volume,
        "limit": limit,
    }


def summarize(db: Session, horizon_days: int, category: str | None = None) -> dict:
    """Scorecard for one horizon: vanta vs market vs the no-skill base-rate
    benchmark, plus the honest-framing fields (coverage of the resolved
    corpus, source counts, median volume) that keep the headline number from
    being quoted out of context."""
    _price_column(horizon_days)  # validates the horizon
    stmt = (
        select(BacktestPrediction, MarketEvent)
        .join(MarketEvent, BacktestPrediction.event_id == MarketEvent.id)
        .where(BacktestPrediction.horizon_days == horizon_days)
    )
    corpus_stmt = select(func.count()).select_from(MarketEvent).where(MarketEvent.outcome.is_not(None))
    if category:
        stmt = stmt.where(MarketEvent.category == category)
        corpus_stmt = corpus_stmt.where(MarketEvent.category == category)
    rows = db.execute(stmt).all()
    n_resolved = db.scalar(corpus_stmt) or 0

    summary: dict = {
        "horizon_days": horizon_days,
        "category": category,
        "n": len(rows),
        "n_resolved_corpus": n_resolved,
        "coverage": round(len(rows) / n_resolved, 4) if n_resolved else 0.0,
    }
    if not rows:
        summary.update(
            vanta_brier=None,
            market_brier=None,
            vanta_log=None,
            market_log=None,
            vanta_accuracy=None,
            market_accuracy=None,
            base_rate_brier=None,
            outcome_base_rate=None,
            sources={},
            median_volume_usd=None,
            calibration=[],
        )
        return summary

    vanta_pairs = [(p.vanta_probability, p.outcome) for p, _ in rows]
    market_pairs = [(p.market_probability, p.outcome) for p, _ in rows]
    outcome_rate = sum(o for _, o in vanta_pairs) / len(vanta_pairs)
    sources: dict[str, int] = {}
    for _, event in rows:
        sources[event.source] = sources.get(event.source, 0) + 1

    vanta_bins = calibration_bins(vanta_pairs)
    market_bins = calibration_bins(market_pairs)
    summary.update(
        vanta_brier=round(brier_score(vanta_pairs), 4),
        market_brier=round(brier_score(market_pairs), 4),
        vanta_log=round(log_score(vanta_pairs), 4),
        market_log=round(log_score(market_pairs), 4),
        vanta_accuracy=round(directional_accuracy(vanta_pairs), 4),
        market_accuracy=round(directional_accuracy(market_pairs), 4),
        # No-skill benchmark: always predict the corpus YES rate.
        base_rate_brier=round(brier_score([(outcome_rate, o) for _, o in vanta_pairs]), 4),
        outcome_base_rate=round(outcome_rate, 4),
        sources=sources,
        median_volume_usd=round(statistics.median(event.volume_usd for _, event in rows), 2),
        calibration=[
            {
                "mid": v.mid,
                "vanta_mean_predicted": v.mean_predicted,
                "vanta_observed_rate": v.observed_rate,
                "vanta_count": v.count,
                "market_mean_predicted": m.mean_predicted,
                "market_observed_rate": m.observed_rate,
                "market_count": m.count,
            }
            for v, m in zip(vanta_bins, market_bins, strict=True)
        ],
    )
    return summary
