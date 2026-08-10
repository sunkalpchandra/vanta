"""Shared agent contract.

Every agent is an independent reasoning module: it receives the question
context (plus outputs of earlier agents where relevant) and returns an
AgentOutput. The orchestrator wires them into a pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class QuestionContext:
    question: str
    category: str
    horizon_days: int
    market_probability: float
    market_volume_usd: float
    market_liquidity: str
    evidence: list[dict] = field(default_factory=list)  # {source, summary, sentiment, impact}
    # Learned category base rate (static prior blended with the resolved
    # record). None => agents fall back to the static prior. Computed by the
    # service layer so the pipeline itself stays DB-free.
    base_rate: float | None = None
    # False => agents skip LLM narration and use template text. Set by
    # counterfactual machinery (sensitivity analysis) that runs the pipeline
    # many times and only needs the numbers.
    narratives: bool = True
    # Analog corpus override. None => the quant agent matches against the
    # built-in REFERENCE_EVENTS. The real-market backtest passes [] because
    # that fixture hard-codes real-world outcomes — matching a 2024 market
    # against a fixture that KNOWS the 2024 outcome is hindsight.
    analog_corpus: list | None = None


@dataclass
class AgentOutput:
    agent: str
    stance: str  # bull | bear | neutral
    probability: float | None  # None for agents that don't estimate directly
    weight: float  # weight in the Bayesian pool (0 => not pooled)
    argument: str
    details: dict = field(default_factory=dict)


class Agent(ABC):
    name: str = "agent"

    @abstractmethod
    def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput: ...
