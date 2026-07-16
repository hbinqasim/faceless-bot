"""Result object returned by Vice Studio agents."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    message: str
    output_path: str | None = None
    execution_time: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
