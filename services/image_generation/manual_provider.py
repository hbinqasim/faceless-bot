"""Manual provider for preparing prompts without external API calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .provider_base import ProviderBase
except ImportError:  # pragma: no cover - supports direct script execution.
    from provider_base import ProviderBase


class ManualProvider(ProviderBase):
    """Write prompt and metadata files for manual image generation."""

    def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prompt_path = Path(output_path).with_suffix(".txt")
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt.strip() + "\n", encoding="utf-8")

        metadata_path = self._metadata_path_for(prompt_path)
        metadata_payload = dict(metadata or {})
        metadata_payload.update(
            {
                "provider": "manual",
                "prompt_path": str(prompt_path),
                "metadata_path": str(metadata_path),
                "status": "prepared",
            }
        )

        metadata_path.write_text(
            json.dumps(metadata_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return {
            "prompt_path": str(prompt_path),
            "metadata_path": str(metadata_path),
            "status": "prepared",
        }

    @staticmethod
    def _metadata_path_for(prompt_path: Path) -> Path:
        if prompt_path.stem.endswith("_prompt"):
            metadata_name = f"{prompt_path.stem[:-7]}_metadata.json"
        else:
            metadata_name = f"{prompt_path.stem}_metadata.json"

        return prompt_path.with_name(metadata_name)
