"""Historian Agent — category base rates and horizon effects."""

from ..quant.bayes import inv_logit, logit
from .base import Agent, AgentOutput, QuestionContext

# Long-run base rates: how often affirmatively-phrased questions in each
# category have historically resolved YES.
CATEGORY_BASE_RATES: dict[str, float] = {
    "finance": 0.52,
    "technology": 0.44,
    "politics": 0.38,
    "science": 0.30,
    "sports": 0.50,
    "crypto": 0.41,
}
DEFAULT_BASE_RATE = 0.42


def base_rate_for(category: str) -> float:
    return CATEGORY_BASE_RATES.get(category, DEFAULT_BASE_RATE)


class HistorianAgent(Agent):
    name = "historian"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        base = ctx.base_rate if ctx.base_rate is not None else base_rate_for(ctx.category)
        # Long horizons leave more room for surprises: pull the market's
        # current read toward the category base rate as horizon grows.
        horizon_pull = min(0.5, ctx.horizon_days / 720)
        z = (1 - horizon_pull) * logit(ctx.market_probability) + horizon_pull * logit(base)
        probability = inv_logit(z)
        stance = (
            "bear" if probability < ctx.market_probability - 0.02
            else "bull" if probability > ctx.market_probability + 0.02
            else "neutral"
        )
        argument = (
            f"Historically, {ctx.category} questions of this shape resolve YES about {base:.0%} of the time. "
            f"With a {ctx.horizon_days}-day horizon, the base rate pulls the current market read "
            f"{'down' if stance == 'bear' else 'up' if stance == 'bull' else 'only marginally'} "
            f"to {probability:.0%}."
        )
        return AgentOutput(
            agent=self.name,
            stance=stance,
            probability=probability,
            weight=0.7,
            argument=argument,
            details={"base_rate": base, "horizon_days": ctx.horizon_days},
        )
