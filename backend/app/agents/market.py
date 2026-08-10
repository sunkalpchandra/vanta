"""Market Agent — reads the prediction-market consensus and how much to trust it."""

from .base import Agent, AgentOutput, QuestionContext

LIQUIDITY_WEIGHT = {"high": 1.3, "medium": 1.0, "low": 0.6}


class MarketAgent(Agent):
    name = "market"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        weight = LIQUIDITY_WEIGHT.get(ctx.market_liquidity, 1.0)
        if ctx.market_volume_usd >= 1_000_000:
            weight += 0.2
        cents = round(ctx.market_probability * 100)
        argument = (
            f"Prediction markets price YES at {cents}¢ on "
            f"${ctx.market_volume_usd:,.0f} volume with {ctx.market_liquidity} liquidity — "
            f"an implied {cents}% probability. "
            + (
                "Deep liquidity makes this a strong prior."
                if weight >= 1.3
                else "Thin liquidity means the price can be moved by few traders; treated as a weak prior."
                if weight < 1.0
                else "A reasonable but not decisive prior."
            )
        )
        return AgentOutput(
            agent=self.name,
            stance="neutral",
            probability=ctx.market_probability,
            weight=weight,
            argument=argument,
            details={
                "market_probability": ctx.market_probability,
                "volume_usd": ctx.market_volume_usd,
                "liquidity": ctx.market_liquidity,
            },
        )
