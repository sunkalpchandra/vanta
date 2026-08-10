"""Pipeline orchestrator.

Runs the agent chain in dependency order:

    research -> quant -> market -> sentiment -> historian  (independent estimators)
                                -> skeptic                 (attacks the interim consensus)
                                -> synthesis               (final pooled forecast)
"""

from dataclasses import dataclass, field

from .base import Agent, AgentOutput, QuestionContext
from .historian import HistorianAgent
from .market import MarketAgent
from .quant_agent import QuantAgent
from .research import ResearchAgent
from .sentiment import SentimentAgent
from .skeptic import SkepticAgent
from .synthesis import SynthesisAgent


@dataclass
class PipelineResult:
    probability: float
    confidence: float
    reasoning: str
    risk_factors: list[str]
    edge: float
    outputs: list[AgentOutput] = field(default_factory=list)


ESTIMATORS: list[Agent] = [
    ResearchAgent(),
    QuantAgent(),
    MarketAgent(),
    SentimentAgent(),
    HistorianAgent(),
]


def run_pipeline(ctx: QuestionContext) -> PipelineResult:
    outputs: list[AgentOutput] = []
    for agent in ESTIMATORS:
        outputs.append(agent.run(ctx, outputs))
    outputs.append(SkepticAgent().run(ctx, outputs))
    final = SynthesisAgent().run(ctx, outputs)
    outputs.append(final)
    return PipelineResult(
        probability=round(final.probability, 4),
        confidence=final.details["confidence"],
        reasoning=final.argument,
        risk_factors=final.details["risk_factors"],
        edge=final.details["edge"],
        outputs=outputs,
    )
