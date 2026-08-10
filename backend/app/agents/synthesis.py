"""Synthesis Agent — weighted Bayesian aggregation into the final forecast."""

from dataclasses import dataclass, field

from ..llm import narrate
from ..quant.bayes import agreement_confidence, pool, shrink_to_base_rate
from .agents_util import find_output
from .base import Agent, AgentOutput, QuestionContext
from .historian import base_rate_for


@dataclass
class FinalForecast:
    probability: float
    confidence: float
    reasoning: str
    risk_factors: list[str] = field(default_factory=list)


class SynthesisAgent(Agent):
    name = "synthesis"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        estimates = [
            (o.probability, o.weight)
            for o in prior_outputs
            if o.probability is not None and o.weight > 0
        ]
        pooled = pool(estimates)
        base = ctx.base_rate if ctx.base_rate is not None else base_rate_for(ctx.category)
        final_p = shrink_to_base_rate(pooled, base, strength=0.12)

        confidence = agreement_confidence(estimates, pooled)
        skeptic = find_output(prior_outputs, "skeptic")
        risk_factors: list[str] = []
        if skeptic:
            confidence = max(1.0, round(confidence - skeptic.details.get("confidence_haircut", 0.0), 1))
            risk_factors = skeptic.details.get("risk_factors", [])

        edge = final_p - ctx.market_probability
        contributions = "; ".join(
            f"{o.agent} {o.probability:.0%} (w={o.weight:.1f})"
            for o in prior_outputs
            if o.probability is not None and o.weight > 0
        )
        fallback = (
            f"Weighted log-odds pooling of {len(estimates)} agent estimates ({contributions}), "
            f"shrunk toward the {ctx.category} base rate, yields {final_p:.0%} — "
            f"{'an edge of ' + format(edge, '+.0%') + ' versus' if abs(edge) >= 0.02 else 'in line with'} "
            f"the market at {ctx.market_probability:.0%}."
        )
        reasoning = narrate(
            system=(
                "You are the Synthesis Agent of a forecasting intelligence system. Write a crisp 2-4 sentence "
                "final rationale for the given probability. Mention the strongest driver and the main caveat. "
                "Do not change the numbers. No preamble."
            ),
            prompt=(
                f"Question: {ctx.question}\nFinal probability: {final_p:.0%} "
                f"(market: {ctx.market_probability:.0%}).\nAgent estimates: {contributions}.\n"
                f"Risks: {risk_factors}"
            ),
            fallback=fallback,
        )
        stance = "bull" if edge > 0.02 else "bear" if edge < -0.02 else "neutral"
        return AgentOutput(
            agent=self.name,
            stance=stance,
            probability=final_p,
            weight=0.0,  # output, not a pool input
            argument=reasoning,
            details={
                "confidence": confidence,
                "risk_factors": risk_factors,
                "edge": round(edge, 4),
                "pooled_before_shrinkage": round(pooled, 4),
            },
        )
