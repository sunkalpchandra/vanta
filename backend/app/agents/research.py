"""Research Agent — weighs qualitative evidence for and against the event."""

from ..llm import narrate
from ..quant.bayes import inv_logit, logit
from .base import Agent, AgentOutput, QuestionContext


class ResearchAgent(Agent):
    name = "research"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        positive = [e for e in ctx.evidence if e["sentiment"] == "positive"]
        negative = [e for e in ctx.evidence if e["sentiment"] == "negative"]
        pos_w = sum(e["impact"] for e in positive)
        neg_w = sum(e["impact"] for e in negative)
        # Net evidence tilt in [-1, 1], damped by a +1 pseudo-count.
        tilt = (pos_w - neg_w) / (pos_w + neg_w + 1.0)
        probability = inv_logit(logit(ctx.market_probability) + tilt * 1.2)
        stance = "bull" if tilt > 0.08 else "bear" if tilt < -0.08 else "neutral"

        fallback = self._template_argument(positive, negative, tilt)
        argument = narrate(
            system=(
                "You are the Research Agent of a forecasting intelligence system. "
                "Write a tight 2-3 sentence evidence assessment. No preamble."
            ),
            prompt=(
                f"Question: {ctx.question}\n"
                f"Supporting evidence: {[e['summary'] for e in positive]}\n"
                f"Opposing evidence: {[e['summary'] for e in negative]}\n"
                f"Net tilt: {tilt:+.2f}"
            ),
            fallback=fallback,
        )
        return AgentOutput(
            agent=self.name,
            stance=stance,
            probability=probability,
            weight=1.0 + min(1.0, pos_w + neg_w) * 0.5,
            argument=argument,
            details={
                "supporting": [e["summary"] for e in positive],
                "opposing": [e["summary"] for e in negative],
                "net_tilt": round(tilt, 3),
            },
        )

    @staticmethod
    def _template_argument(positive: list[dict], negative: list[dict], tilt: float) -> str:
        direction = "supports" if tilt > 0 else "cuts against" if tilt < 0 else "is balanced on"
        strongest = max(positive + negative, key=lambda e: e["impact"], default=None)
        lead = f"The evidence base ({len(positive)} supporting, {len(negative)} opposing signals) {direction} the event."
        if strongest:
            lead += f" The single strongest signal: {strongest['summary'].rstrip('.')}."
        return lead
