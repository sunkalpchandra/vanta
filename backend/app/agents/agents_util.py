from .base import AgentOutput


def find_output(outputs: list[AgentOutput], agent_name: str) -> AgentOutput | None:
    return next((o for o in outputs if o.agent == agent_name), None)
