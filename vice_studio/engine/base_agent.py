"""Base class for Vice Studio agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_result import AgentResult
from .logger import get_logger
from .metrics import start_timer, stop_timer
from .resource_loader import load_json, load_text


class BaseAgent:
    """Common execution wrapper for future Vice Studio agents."""

    def __init__(
        self,
        agent_name: str,
        config_path: str | Path | None = None,
        prompt_path: str | Path | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.config_path = config_path
        self.prompt_path = prompt_path
        self.logger = get_logger(agent_name)
        self.config: dict[str, Any] = {}
        self.prompt = ""

    def load_config(self) -> dict[str, Any]:
        """Load the agent JSON configuration, if one was provided."""
        if self.config_path is None:
            self.config = {}
            return self.config

        self.config = load_json(self.config_path)
        return self.config

    def load_prompt(self) -> str:
        """Load the agent prompt text, if one was provided."""
        if self.prompt_path is None:
            self.prompt = ""
            return self.prompt

        self.prompt = load_text(self.prompt_path)
        return self.prompt

    def run(self) -> Any:
        """Run the agent. Subclasses must override this method."""
        raise NotImplementedError("Subclasses must implement run().")

    def execute(self) -> AgentResult:
        """Run the agent with timing, logging, and failure handling."""
        timer = start_timer()

        try:
            self.logger.info("Starting agent: %s", self.agent_name)
            output = self.run()
            execution_time = stop_timer(timer)

            if isinstance(output, AgentResult):
                output.execution_time = output.execution_time or execution_time
                return output

            output_path = str(output) if isinstance(output, (str, Path)) else None
            metadata = {}
            if output is not None and output_path is None:
                metadata["output"] = output

            return AgentResult(
                agent_name=self.agent_name,
                success=True,
                message="Agent completed successfully.",
                output_path=output_path,
                execution_time=execution_time,
                metadata=metadata,
            )
        except Exception as error:
            execution_time = stop_timer(timer)
            self.logger.exception("Agent failed: %s", self.agent_name)
            return AgentResult(
                agent_name=self.agent_name,
                success=False,
                message=str(error),
                execution_time=execution_time,
                errors=[str(error)],
                metadata={"exception_type": error.__class__.__name__},
            )
