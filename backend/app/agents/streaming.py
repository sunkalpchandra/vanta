"""Streaming driver for the agent pipeline.

Re-drives the exact sequence orchestrator.run_pipeline uses — the same agent
instances, the same order, the same final rounding — but yields an event per
step so a caller can forward the debate over SSE as it happens. The math
lives entirely in the agents; this module only interleaves yields, so the
streamed numbers are identical to what run_pipeline (and therefore
service.run_and_store_forecast) computes for the same context. Kept DB-free
like the rest of the pipeline — persistence is the caller's job.
"""

from collections.abc import Iterator
from typing import Any

from .base import AgentOutput, QuestionContext
from .orchestrator import ESTIMATORS
from .skeptic import SkepticAgent
from .synthesis import SynthesisAgent

# (kind, payload): kind is 'agent_start' (payload: agent name),
# 'agent_report' (payload: report dict), or 'forecast' (payload: final dict).
StreamEvent = tuple[str, Any]


def report_payload(output: AgentOutput) -> dict:
    """The JSON-safe shape of one agent's report — mirrors what
    run_and_store_forecast persists into AgentReport rows."""
    return {
        "agent": output.agent,
        "stance": output.stance,
        "probability": output.probability,
        "argument": output.argument,
        "details": output.details,
    }


def stream_pipeline(ctx: QuestionContext) -> Iterator[StreamEvent]:
    """Yield ('agent_start', name) / ('agent_report', payload) per agent in
    pipeline order, then ('forecast', payload) with the final synthesis.

    Each agent sees exactly the prior outputs run_pipeline would hand it:
    the skeptic gets the five estimators, synthesis gets those plus the
    skeptic. The forecast payload matches PipelineResult field-for-field
    (probability rounded to 4, confidence/risk_factors from the synthesis
    details) so parity with a direct run is exact.
    """
    outputs: list[AgentOutput] = []
    for agent in [*ESTIMATORS, SkepticAgent(), SynthesisAgent()]:
        yield ("agent_start", agent.name)
        output = agent.run(ctx, outputs)
        outputs.append(output)
        yield ("agent_report", report_payload(output))
    final = outputs[-1]
    yield (
        "forecast",
        {
            "probability": round(final.probability, 4),
            "confidence": final.details["confidence"],
            "reasoning": final.argument,
            "risk_factors": final.details["risk_factors"],
        },
    )
