"""Quant Agent — historical analog matching + Monte Carlo uncertainty."""

from ..data import REFERENCE_EVENTS
from ..quant.analogs import find_analogs
from ..quant.montecarlo import simulate
from .base import Agent, AgentOutput, QuestionContext


class QuantAgent(Agent):
    name = "quant"

    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput:
        corpus = REFERENCE_EVENTS if ctx.analog_corpus is None else ctx.analog_corpus
        report = find_analogs(ctx.question, ctx.category, corpus)
        if report.hit_rate is None:
            return AgentOutput(
                agent=self.name,
                stance="neutral",
                probability=None,
                weight=0.0,
                argument="No sufficiently similar resolved events in the reference set; the quant model abstains.",
                details={"analogs": [], "hit_rate": None},
            )
        # Clamp away from 0/1: a small analog sample can't justify certainty.
        probability = min(0.95, max(0.05, report.hit_rate))
        sim = simulate(
            probability=probability,
            evidence_strength=4 + report.n,
            market_probability=ctx.market_probability,
        )
        yes_count = sum(m.outcome for m in report.matches)
        stance = (
            "bull" if probability > ctx.market_probability + 0.03
            else "bear" if probability < ctx.market_probability - 0.03
            else "neutral"
        )
        argument = (
            f"Of {report.n} comparable resolved events, {yes_count} resolved YES "
            f"(similarity-weighted rate {report.hit_rate:.0%}). Monte Carlo over the posterior gives a "
            f"90% credible interval of {sim.ci_low:.0%}-{sim.ci_high:.0%}, and {sim.p_above_market:.0%} "
            f"of simulations land above the market's {ctx.market_probability:.0%}."
        )
        return AgentOutput(
            agent=self.name,
            stance=stance,
            probability=probability,
            weight=0.6 + min(0.9, report.n * 0.09),
            argument=argument,
            details={
                "analogs": [
                    {"text": m.text, "similarity": round(m.similarity, 2), "outcome": m.outcome}
                    for m in report.matches[:6]
                ],
                "hit_rate": round(report.hit_rate, 3),
                "n_analogs": report.n,
                "ci_low": round(sim.ci_low, 3),
                "ci_high": round(sim.ci_high, 3),
                "p_above_market": round(sim.p_above_market, 3),
            },
        )
