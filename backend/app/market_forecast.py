"""On-demand forecast + agent debate for a single live market event.

Runs the exact deterministic agent pipeline the leakage-free backtest uses
(``agents.orchestrator.run_pipeline``), but against the event's CURRENT synced
venue price (``event.yes_price``) rather than a T-h snapshot. This is a live
"what does vanta think of this price right now, and why" call — not a scored
backtest — so it echoes ``backtest.context_for`` in every respect except the
market probability it compares against.

Determinism: every NUMBER (probability, edge, per-agent estimates, stances)
comes from the quant engine and is fully deterministic. Narratives are allowed
here because it is a single on-demand call — but with no Anthropic key the
prose is template text either way (``llm.narrate`` falls back), so the whole
result is reproducible offline. The LLM layer never touches a number, same
boundary as the rest of the platform.

play money · paper trading · real market prices — never real money.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .agents.base import QuestionContext
from .agents.orchestrator import run_pipeline
from .backtest import liquidity_for_volume
from .models import MarketEvent
from .service import learned_base_rate

# Divergence bands between vanta and the venue price, in probability points.
# Within AGREE_BAND vanta endorses the price; past DISAGREE_BAND it is a
# material call against the venue; the gap between them is a soft lean.
AGREE_BAND = 0.02
DISAGREE_BAND = 0.05

# Stand-in horizon when an event carries no close_time (undated markets).
DEFAULT_HORIZON_DAYS = 90


def _as_utc(dt: datetime) -> datetime:
    """Coerce to tz-aware UTC. SQLite drops tzinfo despite DateTime(timezone=True)
    (see CLAUDE.md), so a stored datetime can read back naive; normalizing both
    sides keeps the horizon subtraction from mixing naive and aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _horizon_days(event: MarketEvent) -> int:
    """Days from the event's last sync to its close — a deterministic proxy for
    'time left on the market'. Derived from stored timestamps only (never the
    wall clock at call time), so repeated calls are identical. Falls back to
    DEFAULT_HORIZON_DAYS when close_time is unknown and floors at 1 so a market
    at/after close still gets a valid (short) horizon."""
    if event.close_time is None:
        return DEFAULT_HORIZON_DAYS
    reference = event.last_synced or event.ingested_at
    return max(1, (_as_utc(event.close_time) - _as_utc(reference)).days)


def _direction(edge: float) -> str:
    """Where vanta lands relative to the venue price: 'agree' (in line),
    'disagree' (a material edge either way), or 'neutral' (a soft lean)."""
    magnitude = abs(edge)
    if magnitude >= DISAGREE_BAND:
        return "disagree"
    if magnitude < AGREE_BAND:
        return "agree"
    return "neutral"


def forecast_market(db: Session, event: MarketEvent) -> dict:
    """vanta's forecast for one live market event plus the agent debate behind
    it. The context mirrors ``backtest.context_for`` — no evidence (none is
    captured for a live venue market, and fabricating it would be dishonest),
    no analog corpus (REFERENCE_EVENTS hard-codes real outcomes, so matching a
    live market against it is hindsight), category base rate learned from the
    resolved corpus (``service.learned_base_rate``, the same prior the live
    ``build_context`` uses) — but ``market_probability`` is the event's current
    synced ``yes_price`` instead of a leakage-free snapshot.

    Caller must guarantee ``event.yes_price`` is not None (the router 409s
    otherwise); there is nothing to forecast against without a price.
    """
    market_probability = event.yes_price
    volume = event.volume_usd or 0.0
    ctx = QuestionContext(
        question=event.question,
        category=event.category,
        horizon_days=_horizon_days(event),
        market_probability=market_probability,
        market_volume_usd=volume,
        market_liquidity=liquidity_for_volume(volume),
        evidence=[],
        base_rate=round(learned_base_rate(db, event.category), 4),
        narratives=True,
        analog_corpus=[],
    )
    result = run_pipeline(ctx)

    # Compute edge off the RETURNED (rounded) probability so the dict's own
    # invariant holds exactly: probability - market_probability == edge.
    edge = round(result.probability - market_probability, 4)
    return {
        "probability": result.probability,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "risk_factors": result.risk_factors,
        "market_probability": market_probability,
        "edge": edge,
        "direction": _direction(edge),
        "agent_reports": [
            {
                "agent": o.agent,
                "stance": o.stance,
                "probability": o.probability,
                "argument": o.argument,
            }
            for o in result.outputs
        ],
    }
