"""Regression: an agent estimate of exactly 0.0 is a maximally bearish vote,
not an abstention — the truthiness filter used to drop it from the pool."""

from app.agents.base import AgentOutput, QuestionContext
from app.agents.skeptic import SkepticAgent
from app.agents.synthesis import SynthesisAgent

CTX = QuestionContext(
    question="Will this event with a zero-priced market happen?",
    category="finance",
    horizon_days=30,
    market_probability=0.001,
    market_volume_usd=0.0,
    market_liquidity="low",
    evidence=[],
)


def _outputs():
    return [
        AgentOutput(agent="market", stance="neutral", probability=0.0, weight=1.0, argument="x"),
        AgentOutput(agent="quant", stance="bull", probability=0.6, weight=1.0, argument="x"),
    ]


def test_synthesis_includes_zero_probability_estimates():
    outputs = _outputs()
    outputs.append(SkepticAgent().run(CTX, outputs))
    final = SynthesisAgent().run(CTX, outputs)
    # With the 0.0 vote pooled (clamped internally), the result must sit far
    # below the 0.6 estimate; dropping it would pool 0.6 alone -> ~0.55+.
    assert final.probability < 0.30


def test_skeptic_sees_zero_probability_in_interim_consensus():
    skeptic = SkepticAgent().run(CTX, _outputs())
    assert skeptic.details["interim_consensus"] < 0.30
