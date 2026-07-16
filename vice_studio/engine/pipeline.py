"""Pipeline runner for ordered Vice Studio agents."""

from __future__ import annotations

from .agent_result import AgentResult
from .base_agent import BaseAgent
from .logger import get_logger


class Pipeline:
    """Run agents in order and stop at the first failure."""

    def __init__(self) -> None:
        self.agents: list[BaseAgent] = []
        self.logger = get_logger("vice_studio.pipeline")

    def add_agent(self, agent: BaseAgent) -> None:
        """Add an agent to the end of the pipeline."""
        self.agents.append(agent)

    def run(self) -> list[AgentResult]:
        """Execute agents in order, stopping when one fails."""
        results: list[AgentResult] = []

        for agent in self.agents:
            self.logger.info("Running pipeline agent: %s", agent.agent_name)
            result = agent.execute()
            results.append(result)

            if not result.success:
                self.logger.error(
                    "Stopping pipeline after failed agent: %s",
                    agent.agent_name,
                )
                break

        return results
