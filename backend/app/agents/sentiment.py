"""Sentiment Agent — public mood and momentum from social/news signals."""

from ..quant.bayes import inv_logit
from .base import Agent, AgentOutput, QuestionContext


class SentimentAgent(Agent):
    name = "sentiment"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        if not ctx.evidence:
            return AgentOutput(
                agent=self.name,
                stance="neutral",
                probability=None,
                weight=0.0,
                argument="No social or news signal available for this question yet.",
                details={"positive_share": None, "momentum": "flat"},
            )
        total = sum(e["impact"] for e in ctx.evidence)
        pos = sum(e["impact"] for e in ctx.evidence if e["sentiment"] == "positive")
        positive_share = pos / total if total > 0 else 0.5
        # High-impact items dominate chatter; use them as the momentum proxy.
        high_impact = [e for e in ctx.evidence if e["impact"] >= 0.6]
        pos_hi = sum(1 for e in high_impact if e["sentiment"] == "positive")
        momentum = (
            "increasing" if pos_hi > len(high_impact) / 2
            else "decreasing" if high_impact and pos_hi < len(high_impact) / 2
            else "flat"
        )
        # Sentiment is noisy: a mild standalone estimate with a small weight.
        probability = inv_logit((positive_share - 0.5) * 2.2)
        stance = "bull" if positive_share > 0.58 else "bear" if positive_share < 0.42 else "neutral"
        argument = (
            f"Public sentiment runs {positive_share:.0%} positive with {momentum} momentum. "
            "Sentiment is a weak standalone predictor, so it enters the pool at low weight."
        )
        return AgentOutput(
            agent=self.name,
            stance=stance,
            probability=probability,
            weight=0.45,
            argument=argument,
            details={"positive_share": round(positive_share, 3), "momentum": momentum},
        )
