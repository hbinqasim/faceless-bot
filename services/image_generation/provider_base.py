"""Base provider contract for image generation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ProviderBase(ABC):
    """Abstract image generation provider."""

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate or prepare an image output for the given prompt."""
