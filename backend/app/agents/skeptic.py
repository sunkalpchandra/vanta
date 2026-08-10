"""Skeptic Agent — tries to break the emerging consensus.

The skeptic never adds its own probability to the pool. It attacks the interim
consensus: surfacing the strongest opposing evidence, structural risks, and a
confidence haircut proportional to how much the pipeline disagrees internally
and how thin the evidence is.
"""

from ..llm import narrate
from ..quant.bayes import pool
from .base import Agent, AgentOutput, QuestionContext

CATEGORY_RISKS = {
    "finance": "Unexpected macro shocks (rates, energy, geopolitics) can invalidate current pricing overnight.",
    "technology": "Timelines in tech consistently slip; announcement dates are not delivery dates.",
    "politics": "Political questions hinge on a small number of actors whose incentives can flip quickly.",
    "science": "Scientific milestones fail silently — a single unreplicated result can reset the clock.",
    "sports": "Injury and single-elimination variance dominate long-horizon sports outcomes.",
    "crypto": "Crypto pricing is reflexive: flows chase price, so regime changes are abrupt.",
}


class SkepticAgent(Agent):
    name = "skeptic"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        pooled_inputs = [(o.probability, o.weight) for o in prior_outputs if o.probability and o.weight > 0]
        interim = pool(pooled_inputs) if pooled_inputs else ctx.market_probability
        consensus_bullish = interim >= ctx.market_probability

        risks: list[str] = []
        opposing = sorted(
            (e for e in ctx.evidence if e["sentiment"] == ("negative" if consensus_bullish else "positive")),
            key=lambda e: e["impact"],
            reverse=True,
        )
        risks.extend(e["summary"] for e in opposing[:2])
        if ctx.category in CATEGORY_RISKS:
            risks.append(CATEGORY_RISKS[ctx.category])
        if ctx.market_liquidity == "low":
            risks.append("Thin market liquidity: the 'market consensus' here reflects few participants.")
        if len(ctx.evidence) < 4:
            risks.append("Sparse evidence base — the estimate leans heavily on priors and analogs.")

        # Haircut grows with disagreement between vanta and the market and
        # shrinks with evidence depth. Applied to confidence, not probability.
        divergence = abs(interim - ctx.market_probability)
        evidence_depth = sum(e["impact"] for e in ctx.evidence)
        haircut = round(min(2.5, divergence * 6 + max(0.0, 1.2 - evidence_depth * 0.3)), 2)

        fallback = (
            f"The pipeline is {'above' if consensus_bullish else 'below'} the market "
            f"({interim:.0%} vs {ctx.market_probability:.0%}) — before trusting that edge, weigh: "
            + " ".join(risks[:2])
        )
        argument = narrate(
            system=(
                "You are the Skeptic Agent in a forecasting system. In 2-3 sentences, attack the "
                "consensus estimate: hidden assumptions, missing information, model weaknesses. No preamble."
            ),
            prompt=(
                f"Question: {ctx.question}\nConsensus: {interim:.0%} vs market {ctx.market_probability:.0%}.\n"
                f"Known risks: {risks}"
            ),
            fallback=fallback,
        )
        return AgentOutput(
            agent=self.name,
            stance="bear" if consensus_bullish else "bull",
            probability=None,
            weight=0.0,
            argument=argument,
            details={"risk_factors": risks, "confidence_haircut": haircut, "interim_consensus": round(interim, 3)},
        )
